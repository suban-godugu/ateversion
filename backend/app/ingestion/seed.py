from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

from sqlalchemy import delete, select

from app.core.config import get_settings
from app.core.database import SessionLocal, init_db
from app.ingestion.wafer_image_ingest import find_wafer_image, image_to_die_bins
from app.ml.predictive_maintenance.models import PredictRequest, TelemetryFeature
from app.ml.predictive_maintenance.service import PredictiveMaintenanceService
from app.models.entities import (
    Alert,
    AuditLog,
    DashboardState,
    Die,
    DieTestResult,
    FloorEventView,
    KpiMetric,
    LimitAdjustmentRecord,
    LimitApprovalRecord,
    LimitAuditRecord,
    Lot,
    MaintenanceAsset,
    MaintenanceHistory,
    MaintenancePredictionRow,
    OptimizationMetricHistory,
    PatternOptimizationResult,
    TelemetryEventRow,
    TelemetryFeatureRow,
    TestLimitRecord,
    TestRun,
    Tester,
    TesterSite,
    Wafer,
    WaferMetric,
)
from app.services.test_limits.engine import calculate_cpk, change_label
from app.services.test_limits.models import LimitDirection
from app.schemas.events import EventType, TelemetryEvent
from app.services.telemetry_service import ingest_events

LOT_ID = "24601-07"
WAFER_ID = "W-24601-07"
TESTER_ID = "ATE-04"

KPI_DEFS = [
    {
        "key": "false_failure_reduction",
        "title": "False Failure Reduction",
        "value": 32.4,
        "previous": 31.8,
        "unit": "%",
        "baseline": 28.0,
        "target": 35.0,
        "description": "Marginal fails re-scored against correlation history before being counted, not just re-tested.",
        "accent": "#6EE7A8",
    },
    {
        "key": "test_time_reduction",
        "title": "Test Time Reduction",
        "value": 21.2,
        "previous": 20.5,
        "unit": "%",
        "baseline": 15.0,
        "target": 25.0,
        "description": "Adaptive pattern ordering skips low-probability-of-fail sequences per device signature.",
        "accent": "#6BC1F2",
    },
    {
        "key": "yield_improvement",
        "title": "Yield Improvement",
        "value": 2.6,
        "previous": 2.4,
        "unit": "pts",
        "baseline": 1.5,
        "target": 3.0,
        "description": "Net gain versus static-limit baseline, attributable to false-fail and limit optimization.",
        "accent": "#6EE7A8",
    },
    {
        "key": "retest_reduction",
        "title": "Retest Reduction",
        "value": 38.1,
        "previous": 36.9,
        "unit": "%",
        "baseline": 30.0,
        "target": 40.0,
        "description": "Retest insertions triggered only when statistically warranted by confidence scoring.",
        "accent": "#F2B155",
    },
    {
        "key": "escape_prevention",
        "title": "Escape Prevention",
        "value": 99.92,
        "previous": 99.90,
        "unit": "%",
        "baseline": 99.80,
        "target": 99.95,
        "description": "Outlier-pattern screening catches latent defects that pass standard go/no-go limits.",
        "accent": "#F0667A",
    },
    {
        "key": "vector_memory_optimization",
        "title": "Vector Memory Optimization",
        "value": 29.3,
        "previous": 28.1,
        "unit": "%",
        "baseline": 20.0,
        "target": 32.0,
        "description": "Don't-care bit compression and pattern reuse reduce ATE vector memory footprint.",
        "accent": "#6BC1F2",
    },
    {
        "key": "pattern_count_reduction",
        "title": "Pattern Count Reduction",
        "value": 24.1,
        "previous": 23.0,
        "unit": "%",
        "baseline": 18.0,
        "target": 28.0,
        "description": "Redundant-pattern elimination via coverage-preserving ATPG analysis.",
        "accent": "#6BC1F2",
    },
    {
        "key": "m_bist_shmoo",
        "title": "SHMOO ML-Based Optimization",
        "value": 96.2,
        "previous": 95.1,
        "unit": "%",
        "baseline": 90.0,
        "target": 95.0,
        "description": "SHMOO ML — Yield Analysis, Debugging, Binning, and Characterization via VDD × Frequency boundary extraction.",
        "accent": "#A78BFA",
    },
]

MAINTENANCE_FEATURES = [
    TelemetryFeature(
        tester_id="ATE-04",
        component="Site 2 probe card",
        test_failures=3,
        parametric_drift=1.1,
        contact_resistance=0.35,
        temperature=38,
        voltage_deviation=0.02,
        current_deviation=0.03,
        cycle_count=12000,
        historical_failures=1,
        maintenance_events=4,
        tester_utilization=0.55,
    ),
    TelemetryFeature(
        tester_id="ATE-07",
        component="Contactor bank B",
        test_failures=18,
        parametric_drift=5.2,
        contact_resistance=1.6,
        temperature=72,
        voltage_deviation=0.11,
        current_deviation=0.14,
        cycle_count=62000,
        historical_failures=9,
        maintenance_events=2,
        tester_utilization=0.88,
    ),
    TelemetryFeature(
        tester_id="ATE-11",
        component="Site 5 probe card",
        test_failures=24,
        parametric_drift=6.1,
        contact_resistance=1.9,
        temperature=78,
        voltage_deviation=0.14,
        current_deviation=0.18,
        cycle_count=71000,
        historical_failures=12,
        maintenance_events=1,
        tester_utilization=0.93,
    ),
    TelemetryFeature(
        tester_id="ATE-02",
        component="Contactor bank A",
        test_failures=2,
        parametric_drift=0.8,
        contact_resistance=0.28,
        temperature=35,
        voltage_deviation=0.015,
        current_deviation=0.02,
        cycle_count=9000,
        historical_failures=0,
        maintenance_events=5,
        tester_utilization=0.48,
    ),
]


def _history_from_base(base: float, n: int = 24) -> tuple[list[float], list[dict]]:
    # Deterministic mild walk from base (no random)
    series: list[float] = []
    history: list[dict] = []
    now = datetime.utcnow()
    for i in range(n):
        delta = ((i % 5) - 2) * 0.05
        v = round(base + delta + (i * 0.01), 3)
        series.append(v)
        history.append(
            {
                "timestamp": (now - timedelta(hours=(n - i))).isoformat(),
                "value": v,
            }
        )
    return series, history


async def ensure_missing_kpi_defs(db) -> int:
    """Insert missing KPI_DEFS rows and sync titles for existing ones."""
    from app.services.kpi_service import compute_improvement, compute_status, compute_trend

    added = 0
    changed = False
    for defn in KPI_DEFS:
        existing = await db.get(KpiMetric, defn["key"])
        if existing is not None:
            if existing.title != defn["title"]:
                existing.title = defn["title"]
                changed = True
            if getattr(existing, "description", None) != defn.get("description"):
                existing.description = defn.get("description")
                changed = True
            continue
        value = float(defn["value"])
        previous = float(defn["previous"])
        baseline = float(defn["baseline"])
        target = float(defn["target"])
        series, history = _history_from_base(value)
        db.add(
            KpiMetric(
                key=defn["key"],
                title=defn["title"],
                value=value,
                unit=defn["unit"],
                baseline=baseline,
                target=target,
                previous_value=previous,
                improvement=compute_improvement(value, previous),
                status=compute_status(value, baseline, target),
                description=defn["description"],
                accent=defn["accent"],
                trend=compute_trend(value, previous),
                series=series,
                history=history,
            )
        )
        for point in history:
            ts_raw = point.get("t") or point.get("timestamp")
            val = point.get("v", point.get("value", value))
            db.add(
                OptimizationMetricHistory(
                    history_id=str(uuid4()),
                    metric_id=defn["key"],
                    value=float(val),
                    timestamp=datetime.fromisoformat(ts_raw)
                    if isinstance(ts_raw, str)
                    else datetime.utcnow(),
                    source="ensure",
                )
            )
        added += 1
        changed = True
    if changed:
        await db.commit()
    return added


async def clear_all(db) -> None:
    # Children first (respect FK order)
    for model in (
        Alert,
        AuditLog,
        FloorEventView,
        TelemetryEventRow,
        DieTestResult,
        WaferMetric,
        OptimizationMetricHistory,
        PatternOptimizationResult,
        LimitAuditRecord,
        LimitApprovalRecord,
        LimitAdjustmentRecord,
        TestLimitRecord,
        MaintenanceHistory,
        MaintenancePredictionRow,
        TelemetryFeatureRow,
        MaintenanceAsset,
        TestRun,
        Die,
        Wafer,
        Lot,
        KpiMetric,
        Tester,
        TesterSite,
        DashboardState,
    ):
        await db.execute(delete(model))
    await db.commit()
    # Fresh singleton projection row
    db.add(DashboardState(id=1, lots_in_test=0, test_time_saved_hours=0.0, overall_yield_pct=0.0))
    await db.commit()


async def seed() -> None:
    settings = get_settings()
    await init_db()
    async with SessionLocal() as db:
        await clear_all(db)

        # Baseline KPI rows (authoritative DB values — all math in Python)
        from app.services.kpi_service import compute_improvement, compute_status, compute_trend

        for defn in KPI_DEFS:
            value = float(defn["value"])
            previous = float(defn["previous"])
            baseline = float(defn["baseline"])
            target = float(defn["target"])
            series, history = _history_from_base(value)
            db.add(
                KpiMetric(
                    key=defn["key"],
                    title=defn["title"],
                    value=value,
                    unit=defn["unit"],
                    baseline=baseline,
                    target=target,
                    previous_value=previous,
                    improvement=compute_improvement(value, previous),
                    status=compute_status(value, baseline, target),
                    description=defn["description"],
                    accent=defn["accent"],
                    trend=compute_trend(value, previous),
                    series=series,
                    history=history,
                )
            )
            for point in history:
                ts_raw = point.get("t") or point.get("timestamp")
                val = point.get("v", point.get("value", value))
                db.add(
                    OptimizationMetricHistory(
                        history_id=str(uuid4()),
                        metric_id=defn["key"],
                        value=float(val),
                        timestamp=datetime.fromisoformat(ts_raw)
                        if isinstance(ts_raw, str)
                        else datetime.utcnow(),
                        source="seed",
                    )
                )
        await db.commit()

        # Sites → Testers → Lot (FK order)
        for sid, sname in [("1", "Site 1"), ("3", "Site 3")]:
            db.add(TesterSite(site_id=sid, name=sname, fab="Local Fab", status="active"))
        for tid, name in [
            ("ATE-04", "ATE-04"),
            ("ATE-07", "ATE-07"),
            ("ATE-11", "ATE-11"),
            ("ATE-02", "ATE-02"),
        ]:
            db.add(Tester(tester_id=tid, name=name, status="online", site_id="1"))
        db.add(
            Lot(
                lot_id=LOT_ID,
                status="active",
                tester_id=TESTER_ID,
                site_id="1",
                started_at=datetime.utcnow(),
            )
        )
        await db.commit()

        seq = 1
        now = datetime.utcnow()
        events: list[TelemetryEvent] = []

        events.append(
            TelemetryEvent(
                event_id=str(uuid4()),
                event_type=EventType.lot_started,
                timestamp=now - timedelta(hours=2),
                source="seed",
                tester_id=TESTER_ID,
                site_id="1",
                lot_id=LOT_ID,
                wafer_id=None,
                die_id=None,
                sequence_number=seq,
                payload={},
            )
        )
        seq += 1

        dataset = settings.wafer_dataset_root
        image_path = find_wafer_image(dataset) if dataset else None
        if image_path is None:
            # Deterministic geometric fallback grid (still server-side, not browser RNG)
            dies = []
            rows = cols = 15
            cx = cy = 7
            for y in range(rows):
                for x in range(cols):
                    dist = ((x - cx) ** 2 + (y - cy) ** 2) ** 0.5
                    if dist > 7.2:
                        continue
                    if dist > 6.2:
                        b = "fail" if (x + y) % 5 == 0 else "retest" if (x + y) % 3 == 0 else "pass"
                    elif dist > 5.0 and (x * 3 + y) % 11 == 0:
                        b = "reclass"
                    else:
                        b = "pass"
                    dies.append({"x": x, "y": y, "bin": b, "die_id": f"{x},{y}"})
            source_label = "synthetic_grid"
        else:
            dies = image_to_die_bins(Path(image_path))
            source_label = str(image_path.name)

        events.append(
            TelemetryEvent(
                event_id=str(uuid4()),
                event_type=EventType.wafer_started,
                timestamp=now - timedelta(hours=1, minutes=50),
                source="ingestion",
                tester_id=TESTER_ID,
                site_id="1",
                lot_id=LOT_ID,
                wafer_id=WAFER_ID,
                die_id=None,
                sequence_number=seq,
                payload={
                    "total_dies": len(dies),
                    "caption": f"Live wafer map · Lot {LOT_ID}",
                    "source_image": source_label,
                },
            )
        )
        seq += 1

        bin_to_event = {
            "pass": EventType.die_pass,
            "fail": EventType.die_fail,
            "retest": EventType.die_retest,
            "reclass": EventType.die_reclassified,
        }

        for i, die in enumerate(dies):
            et = bin_to_event[die["bin"]]
            x, y, b = int(die["x"]), int(die["y"]), die["bin"]
            fail_code = {"fail": "BIN_FAIL", "retest": "MARGINAL", "reclass": "FF_OVERTURN"}.get(b)
            confidence = {"pass": 0.97, "reclass": 0.91, "retest": 0.72, "fail": 0.88}.get(b, 0.5)
            events.append(
                TelemetryEvent(
                    event_id=str(uuid4()),
                    event_type=et,
                    timestamp=now - timedelta(hours=1, minutes=40) + timedelta(seconds=i),
                    source="stdf",
                    tester_id=TESTER_ID,
                    site_id="1",
                    lot_id=LOT_ID,
                    wafer_id=WAFER_ID,
                    die_id=die["die_id"],
                    sequence_number=seq,
                    payload={
                        "x": x,
                        "y": y,
                        "bin": b,
                        "pattern_group": 12,
                        "fail_code": fail_code,
                        "test_time_ms": float(120 + x * 7 + y * 3),
                        "confidence": confidence,
                    },
                )
            )
            seq += 1

        # Yield / test time
        pass_c = sum(1 for d in dies if d["bin"] == "pass")
        reclass_c = sum(1 for d in dies if d["bin"] == "reclass")
        fail_c = sum(1 for d in dies if d["bin"] == "fail")
        retest_c = sum(1 for d in dies if d["bin"] == "retest")
        tested = len(dies)
        yield_pct = round(((pass_c + reclass_c) / tested) * 100, 1) if tested else 0.0

        events.append(
            TelemetryEvent(
                event_id=str(uuid4()),
                event_type=EventType.yield_updated,
                timestamp=now - timedelta(minutes=30),
                source="ingestion",
                tester_id=TESTER_ID,
                site_id="1",
                lot_id=LOT_ID,
                wafer_id=WAFER_ID,
                die_id=None,
                sequence_number=seq,
                payload={
                    "yield_pct": yield_pct,
                    "pass": pass_c,
                    "fail": fail_c,
                    "retest": retest_c,
                    "reclass": reclass_c,
                    "total": tested,
                },
            )
        )
        seq += 1

        events.append(
            TelemetryEvent(
                event_id=str(uuid4()),
                event_type=EventType.test_time_updated,
                timestamp=now - timedelta(minutes=28),
                source="ate",
                tester_id=TESTER_ID,
                site_id="1",
                lot_id=LOT_ID,
                wafer_id=WAFER_ID,
                die_id=None,
                sequence_number=seq,
                payload={"hours_saved_24h": 214.0, "reduction_pct": 21.2},
            )
        )
        seq += 1

        # Authoritative dynamic test limits (Python intelligence — not client-computed)
        import random as _rnd

        _rng = _rnd.Random(42)
        limit_defs = [
            {
                "limit_id": "lim-vdd",
                "parameter": "VDD leakage",
                "test_name": "Site 3",
                "site_id": "3",
                "previous": 1.20e-6,
                "current": 1.15e-6,
                "direction": "tightened",
                "usl": 1.15e-6,
                "lsl": None,
                "is_upper": True,
                "mean": 0.72e-6,
                "std": 0.09e-6,
                "status": "ACTIVE",
            },
            {
                "limit_id": "lim-iddq",
                "parameter": "Iddq quiescent",
                "test_name": f"Lot {LOT_ID.split('-')[0]}",
                "site_id": "1",
                "previous": 4.80e-3,
                "current": 4.90e-3,
                "direction": "widened",
                "usl": 4.90e-3,
                "lsl": None,
                "is_upper": True,
                "mean": 3.10e-3,
                "std": 0.45e-3,
                "status": "PENDING_APPROVAL",
            },
            {
                "limit_id": "lim-fmax",
                "parameter": "Fmax shmoo",
                "test_name": "Site 1",
                "site_id": "1",
                "previous": 2.450,
                "current": 2.406,
                "direction": "tightened",
                "usl": None,
                "lsl": 2.406,
                "is_upper": False,
                "mean": 2.62,
                "std": 0.04,
                "status": "ACTIVE",
            },
        ]
        limits = limit_defs
        for ld in limit_defs:
            samples = [
                round(ld["mean"] + _rng.gauss(0, ld["std"]), 9) for _ in range(60)
            ]
            usl = ld["usl"] if ld["usl"] is not None else (ld["current"] if ld["is_upper"] else None)
            lsl = ld["lsl"] if ld["lsl"] is not None else (ld["current"] if not ld["is_upper"] else None)
            cpk = calculate_cpk(samples, lsl=lsl, usl=usl)
            prev = float(ld["previous"])
            cur = float(ld["current"])
            delta = round(cur - prev, 9)
            change_pct = round((delta / abs(prev)) * 100.0, 4) if prev else 0.0
            direction = LimitDirection(ld["direction"])
            label = change_label(direction, change_pct)
            created = now - timedelta(hours=2)
            updated = now - timedelta(minutes=15)
            adj_id = str(uuid4())
            row = TestLimitRecord(
                limit_id=ld["limit_id"],
                parameter=ld["parameter"],
                test_name=ld["test_name"],
                site_id=ld["site_id"],
                tester_id=TESTER_ID,
                lot_id=LOT_ID,
                previous_limit=prev,
                current_limit=cur,
                delta=delta,
                change_percentage=change_pct,
                direction=direction.value,
                cpk=cpk,
                target_cpk=1.33,
                confidence=0.86,
                reason=f"Seeded Cpk-driven {direction.value} recommendation ({label}).",
                status=ld["status"],
                is_upper_limit=ld["is_upper"],
                lsl=lsl,
                usl=usl,
                sample_values=samples,
                active_adjustment_id=adj_id,
                created_at=created,
                updated_at=updated,
            )
            db.add(row)
            db.add(
                LimitAdjustmentRecord(
                    adjustment_id=adj_id,
                    limit_id=ld["limit_id"],
                    previous_limit=prev,
                    proposed_limit=cur,
                    delta=delta,
                    change_percentage=change_pct,
                    direction=direction.value,
                    cpk=cpk,
                    target_cpk=1.33,
                    confidence=0.86,
                    reason=row.reason or "",
                    status=ld["status"],
                    created_by="seed",
                    created_at=created,
                )
            )
            db.add(
                LimitAuditRecord(
                    audit_id=str(uuid4()),
                    limit_id=ld["limit_id"],
                    action="seed",
                    actor="seed",
                    detail=row.reason or "seeded",
                    before_status=None,
                    after_status=ld["status"],
                    before_limit=prev,
                    after_limit=cur,
                    created_at=created,
                )
            )
            events.append(
                TelemetryEvent(
                    event_id=str(uuid4()),
                    event_type=EventType.dynamic_limit_updated,
                    timestamp=updated,
                    source="ingestion",
                    tester_id=TESTER_ID,
                    site_id=ld["site_id"],
                    lot_id=LOT_ID,
                    wafer_id=WAFER_ID,
                    die_id=None,
                    sequence_number=seq,
                    payload={
                        "limit_id": ld["limit_id"],
                        "parameter": ld["parameter"],
                        "test_name": ld["test_name"],
                        "previous_limit": prev,
                        "current_limit": cur,
                        "delta": delta,
                        "change_pct": change_pct,
                        "change_percentage": change_pct,
                        "direction": direction.value,
                        "cpk": cpk,
                        "target_cpk": 1.33,
                        "confidence": 0.86,
                        "reason": row.reason,
                        "status": ld["status"],
                        "change_label": label,
                        "action": "seed",
                    },
                )
            )
            seq += 1
        await db.commit()

        events.append(
            TelemetryEvent(
                event_id=str(uuid4()),
                event_type=EventType.pattern_optimization,
                timestamp=now - timedelta(minutes=12),
                source="ingestion",
                tester_id=TESTER_ID,
                site_id="1",
                lot_id=LOT_ID,
                wafer_id=WAFER_ID,
                die_id=None,
                sequence_number=seq,
                payload={
                    "summary": "Vector memory compaction applied to Pattern Set B7 — 31% footprint reduction.",
                    "kpi_updates": {
                        "vector_memory_optimization": 29.3,
                        "pattern_count_reduction": 24.1,
                        "test_time_reduction": 21.2,
                    },
                },
            )
        )
        seq += 1

        events.append(
            TelemetryEvent(
                event_id=str(uuid4()),
                event_type=EventType.escape_risk_detected,
                timestamp=now - timedelta(minutes=10),
                source="ml",
                tester_id=TESTER_ID,
                site_id="1",
                lot_id=LOT_ID,
                wafer_id=WAFER_ID,
                die_id="3,2",
                sequence_number=seq,
                payload={"reason": "outlier_pattern"},
            )
        )
        seq += 1

        events.append(
            TelemetryEvent(
                event_id=str(uuid4()),
                event_type=EventType.optimization_completed,
                timestamp=now - timedelta(minutes=5),
                source="ingestion",
                tester_id=TESTER_ID,
                site_id="1",
                lot_id=LOT_ID,
                wafer_id=WAFER_ID,
                die_id=None,
                sequence_number=seq,
                payload={
                    "summary": "Lot optimization pass complete",
                    "kpi_updates": {
                        "false_failure_reduction": 32.4,
                        "yield_improvement": 2.6,
                        "retest_reduction": 38.1,
                        "escape_prevention": 99.92,
                    },
                },
            )
        )

        pre = [e for e in events if e.event_type in {EventType.lot_started, EventType.wafer_started}]
        die_events = [e for e in events if e.event_type.value.startswith("die_")]
        post = [
            e
            for e in events
            if e not in pre and e not in die_events
        ]
        print(f"Ingesting setup events ({len(pre)})...", flush=True)
        await ingest_events(db, pre, publish=True, materialize_floor_log=True)
        print(f"Ingesting {len(die_events)} die events...", flush=True)
        chunk = 200
        for i in range(0, len(die_events), chunk):
            await ingest_events(db, die_events[i : i + chunk], publish=False, materialize_floor_log=False)
        print(f"Ingesting summary events ({len(post)})...", flush=True)
        await ingest_events(db, post, publish=True, materialize_floor_log=True)

        # Predictive maintenance — store telemetry features and run Python model
        print("Running predictive maintenance model...", flush=True)
        pm = PredictiveMaintenanceService()
        for feat in MAINTENANCE_FEATURES:
            # Historical feature snapshots for health trend (deterministic offsets)
            for step in range(6):
                snap = feat.model_copy(
                    update={
                        "contact_resistance": feat.contact_resistance * (0.92 + 0.02 * step),
                        "cycle_count": feat.cycle_count * (0.85 + 0.03 * step),
                        "parametric_drift": feat.parametric_drift * (0.9 + 0.03 * step),
                        "captured_at": now - timedelta(days=6 - step),
                    }
                )
                db.add(
                    TelemetryFeatureRow(
                        feature_id=str(uuid4()),
                        tester_id=snap.tester_id,
                        component=snap.component,
                        test_failures=snap.test_failures,
                        parametric_drift=snap.parametric_drift,
                        contact_resistance=snap.contact_resistance,
                        temperature=snap.temperature,
                        voltage_deviation=snap.voltage_deviation,
                        current_deviation=snap.current_deviation,
                        cycle_count=snap.cycle_count,
                        historical_failures=snap.historical_failures,
                        maintenance_events=snap.maintenance_events,
                        tester_utilization=snap.tester_utilization,
                        captured_at=snap.captured_at,
                    )
                )
                pred = pm.predict_from_features(snap, tester_online=True)
                pred.timestamp = snap.captured_at
                await pm.persist_prediction(db, pred, snap)
            await db.commit()
            # Latest live prediction + websocket publish
            await pm.run_predict(
                db,
                PredictRequest(features=feat, publish=True),
            )

        # Ensure adjustments_today matches seeded limit events
        state = await db.get(DashboardState, 1)
        if state:
            state.adjustments_today = max(state.adjustments_today, len(limits))
            state.lots_in_test = max(state.lots_in_test, 1)
            await db.commit()

        wafer = await db.get(Wafer, WAFER_ID)
        print(f"Seeded wafer {WAFER_ID}: dies={tested} yield={yield_pct}% image={source_label}")
        print(f"Active wafer present: {wafer is not None}")
        print(f"PM model available: {pm.model.ensure_ready()}", flush=True)


def main() -> None:
    asyncio.run(seed())


if __name__ == "__main__":
    main()
