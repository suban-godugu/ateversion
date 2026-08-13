from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from uuid import uuid4

from app.models.entities import (
    Alert,
    DashboardState,
    Die,
    DieTestResult,
    FloorEventView,
    Lot,
    MaintenanceAsset,
    PatternOptimizationResult,
    TestLimitRecord,
    TestRun,
    Tester,
    TesterSite,
    Wafer,
    WaferMetric,
)
from app.schemas.events import EventType, TelemetryEvent
from app.services.event_text import text_for_event
from app.services.test_events.severity import severity_for_event, tag_from_severity


async def ensure_site(db: AsyncSession, site_id: str | None) -> str | None:
    if not site_id:
        return None
    site = await db.get(TesterSite, site_id)
    if site is None:
        db.add(
            TesterSite(
                site_id=site_id,
                name=f"Site {site_id}",
                fab="Local Fab",
                status="active",
            )
        )
        await db.flush()
    return site_id


async def ensure_tester(
    db: AsyncSession,
    tester_id: str | None,
    *,
    site_id: str | None = None,
    name: str | None = None,
) -> str | None:
    if not tester_id:
        return None
    await ensure_site(db, site_id)
    tester = await db.get(Tester, tester_id)
    if tester is None:
        db.add(
            Tester(
                tester_id=tester_id,
                name=name or tester_id,
                status="online",
                site_id=site_id,
            )
        )
        await db.flush()
    elif site_id and tester.site_id is None:
        tester.site_id = site_id
    return tester_id


async def ensure_lot(
    db: AsyncSession,
    lot_id: str | None,
    *,
    tester_id: str | None = None,
    site_id: str | None = None,
    timestamp: datetime | None = None,
) -> str | None:
    if not lot_id:
        return None
    await ensure_tester(db, tester_id, site_id=site_id)
    lot = await db.get(Lot, lot_id)
    if lot is None:
        db.add(
            Lot(
                lot_id=lot_id,
                status="active",
                tester_id=tester_id,
                site_id=site_id,
                started_at=timestamp,
            )
        )
        await db.flush()
    return lot_id

DIE_BIN_EVENTS = {
    EventType.die_pass: "pass",
    EventType.die_fail: "fail",
    EventType.die_retest: "retest",
    EventType.die_reclassified: "reclass",
    EventType.die_tested: None,
}


async def ensure_dashboard_state(db: AsyncSession) -> DashboardState:
    state = await db.get(DashboardState, 1)
    if state is not None:
        return state
    # merge avoids duplicate PK inserts when the singleton already exists
    state = DashboardState(id=1)
    state = await db.merge(state)
    await db.flush()
    return state


async def recompute_wafer_yield(db: AsyncSession, wafer_id: str) -> Wafer | None:
    wafer = await db.get(Wafer, wafer_id)
    if wafer is None:
        return None

    rows = (
        await db.execute(select(Die.bin, func.count()).where(Die.wafer_id == wafer_id).group_by(Die.bin))
    ).all()
    counts = {bin_name: count for bin_name, count in rows}
    pass_c = counts.get("pass", 0)
    fail_c = counts.get("fail", 0)
    retest_c = counts.get("retest", 0)
    reclass_c = counts.get("reclass", 0)
    untested = counts.get("untested", 0)
    tested = pass_c + fail_c + retest_c + reclass_c
    total = tested + untested
    good = pass_c + reclass_c
    yield_pct = round((good / tested) * 100, 1) if tested else 0.0

    wafer.pass_count = pass_c
    wafer.fail_count = fail_c
    wafer.retest_count = retest_c
    wafer.reclass_count = reclass_c
    wafer.tested_dies = tested
    wafer.total_dies = total if total else wafer.total_dies
    wafer.yield_pct = yield_pct
    wafer.updated_at = datetime.utcnow()
    return wafer


async def apply_event_projections(
    db: AsyncSession,
    event: TelemetryEvent,
    *,
    defer_yield: bool = False,
    materialize_floor_log: bool = True,
) -> None:
    """Update projection tables from a validated telemetry event. Server-authoritative."""
    state = await ensure_dashboard_state(db)
    et = event.event_type
    payload = event.payload or {}

    site_id = await ensure_site(db, event.site_id)
    tester_id = await ensure_tester(db, event.tester_id, site_id=site_id)
    lot_id = await ensure_lot(
        db, event.lot_id, tester_id=tester_id, site_id=site_id, timestamp=event.timestamp
    )

    if et == EventType.lot_started and lot_id:
        lot = await db.get(Lot, lot_id)
        if lot:
            lot.status = "active"
            lot.started_at = event.timestamp
            lot.tester_id = tester_id or lot.tester_id
            lot.site_id = site_id or lot.site_id
        state.lots_in_test = (
            await db.scalar(select(func.count()).select_from(Lot).where(Lot.status == "active"))
        ) or 0

    if et == EventType.lot_completed and lot_id:
        lot = await db.get(Lot, lot_id)
        if lot:
            lot.status = "completed"
            lot.completed_at = event.timestamp
        state.lots_in_test = (
            await db.scalar(select(func.count()).select_from(Lot).where(Lot.status == "active"))
        ) or 0

    if et in {EventType.wafer_started, EventType.wafer_progress} and event.wafer_id:
        await ensure_lot(
            db,
            lot_id or event.lot_id or "UNKNOWN",
            tester_id=tester_id,
            site_id=site_id,
            timestamp=event.timestamp,
        )
        wafer = await db.get(Wafer, event.wafer_id)
        if wafer is None:
            wafer = Wafer(
                wafer_id=event.wafer_id,
                lot_id=lot_id or event.lot_id or "UNKNOWN",
                tester_id=tester_id,
                site_id=site_id,
                status="testing",
                caption=payload.get("caption", f"Live wafer map · Lot {event.lot_id or '—'}"),
                total_dies=int(payload.get("total_dies", 0)),
            )
            db.add(wafer)
            await db.flush()
            db.add(
                TestRun(
                    run_id=str(uuid4()),
                    lot_id=wafer.lot_id,
                    wafer_id=wafer.wafer_id,
                    tester_id=tester_id,
                    site_id=site_id,
                    status="running",
                    started_at=event.timestamp,
                )
            )
        else:
            if "tested_dies" in payload:
                wafer.tested_dies = int(payload["tested_dies"])
            if "total_dies" in payload:
                wafer.total_dies = int(payload["total_dies"])
            if "caption" in payload:
                wafer.caption = str(payload["caption"])
            wafer.tester_id = tester_id or wafer.tester_id
            wafer.site_id = site_id or wafer.site_id
        # Only link after wafer row is persisted (FK)
        if await db.get(Wafer, event.wafer_id) is not None:
            state.active_wafer_id = event.wafer_id

    if et in DIE_BIN_EVENTS and event.wafer_id and event.die_id:
        await ensure_lot(
            db,
            lot_id or event.lot_id or "UNKNOWN",
            tester_id=tester_id,
            site_id=site_id,
            timestamp=event.timestamp,
        )
        if await db.get(Wafer, event.wafer_id) is None:
            db.add(
                Wafer(
                    wafer_id=event.wafer_id,
                    lot_id=lot_id or event.lot_id or "UNKNOWN",
                    tester_id=tester_id,
                    site_id=site_id,
                    status="testing",
                )
            )
            await db.flush()

        bin_name = DIE_BIN_EVENTS[et]
        if bin_name is None:
            bin_name = str(payload.get("bin", "untested"))
        x = int(payload.get("x", -1))
        y = int(payload.get("y", -1))
        if x < 0 or y < 0:
            parts = event.die_id.replace("(", "").replace(")", "").split(",")
            if len(parts) == 2:
                x, y = int(parts[0]), int(parts[1])
        die_pk = f"{event.wafer_id}:{x},{y}"
        fail_code = payload.get("fail_code")
        if fail_code is None:
            fail_code = {
                "fail": "BIN_FAIL",
                "retest": "MARGINAL",
                "reclass": "FF_OVERTURN",
            }.get(bin_name)
        test_time_ms = payload.get("test_time_ms")
        if test_time_ms is None:
            test_time_ms = float(120 + x * 7 + y * 3)
        confidence = payload.get("confidence")
        if confidence is None:
            confidence = {
                "pass": 0.97,
                "reclass": 0.91,
                "retest": 0.72,
                "fail": 0.88,
                "untested": None,
            }.get(bin_name)

        die = await db.get(Die, die_pk)
        if die is None:
            die = Die(
                die_id=die_pk,
                wafer_id=event.wafer_id,
                x=x,
                y=y,
                bin=bin_name,
                fail_code=str(fail_code) if fail_code else None,
                test_time_ms=float(test_time_ms) if test_time_ms is not None else None,
                confidence=float(confidence) if confidence is not None else None,
                tested_at=event.timestamp,
            )
            db.add(die)
        else:
            die.bin = bin_name
            die.fail_code = str(fail_code) if fail_code else None
            die.test_time_ms = float(test_time_ms) if test_time_ms is not None else None
            die.confidence = float(confidence) if confidence is not None else None
            die.tested_at = event.timestamp
            die.updated_at = datetime.utcnow()

        db.add(
            DieTestResult(
                result_id=str(uuid4()),
                die_id=die_pk,
                wafer_id=event.wafer_id,
                lot_id=lot_id or event.lot_id,
                tester_id=tester_id,
                site_id=site_id,
                result=bin_name,
                fail_code=str(fail_code) if fail_code else None,
                test_time_ms=float(test_time_ms) if test_time_ms is not None else None,
                confidence=float(confidence) if confidence is not None else None,
                timestamp=event.timestamp,
                payload=dict(payload),
            )
        )
        if not defer_yield:
            wafer = await recompute_wafer_yield(db, event.wafer_id)
            if wafer:
                state.active_wafer_id = event.wafer_id
                state.overall_yield_pct = wafer.yield_pct
                lot = await db.get(Lot, wafer.lot_id)
                if lot:
                    lot.overall_yield_pct = wafer.yield_pct
        else:
            state.active_wafer_id = event.wafer_id

    if et == EventType.yield_updated:
        if event.wafer_id:
            wafer = await db.get(Wafer, event.wafer_id)
            if wafer and "yield_pct" in payload:
                wafer.yield_pct = float(payload["yield_pct"])
                wafer.pass_count = int(payload.get("pass", wafer.pass_count))
                wafer.fail_count = int(payload.get("fail", wafer.fail_count))
                wafer.retest_count = int(payload.get("retest", wafer.retest_count))
                wafer.reclass_count = int(payload.get("reclass", wafer.reclass_count))
                wafer.total_dies = int(payload.get("total", wafer.total_dies))
                state.overall_yield_pct = wafer.yield_pct
                db.add(
                    WaferMetric(
                        metric_id=str(uuid4()),
                        wafer_id=wafer.wafer_id,
                        lot_id=wafer.lot_id,
                        metric_key="yield_pct",
                        value=float(payload["yield_pct"]),
                        unit="%",
                        timestamp=event.timestamp,
                    )
                )
        elif "yield_pct" in payload:
            state.overall_yield_pct = float(payload["yield_pct"])

    if et == EventType.test_time_updated and "hours_saved_24h" in payload:
        state.test_time_saved_hours = float(payload["hours_saved_24h"])

    if et == EventType.pattern_optimization:
        db.add(
            PatternOptimizationResult(
                result_id=str(uuid4()),
                lot_id=lot_id or event.lot_id,
                wafer_id=event.wafer_id,
                tester_id=tester_id,
                pattern_group=str(payload.get("pattern_group")) if payload.get("pattern_group") else None,
                summary=str(payload.get("summary", "")),
                footprint_reduction_pct=float(payload["footprint_reduction_pct"])
                if payload.get("footprint_reduction_pct") is not None
                else None,
                test_time_reduction_pct=float(payload["test_time_reduction_pct"])
                if payload.get("test_time_reduction_pct") is not None
                else None,
                details=dict(payload),
                created_at=event.timestamp,
            )
        )

    # Explicit kpi_updates in any authoritative event payload always apply.
    # Derived KPI rules remain limited to optimization/yield event types.
    if payload.get("kpi_updates") or et in {
        EventType.pattern_optimization,
        EventType.optimization_completed,
        EventType.test_time_updated,
        EventType.yield_updated,
    }:
        from app.services.kpi_service import apply_kpi_updates_from_event

        await apply_kpi_updates_from_event(db, et.value, payload, at=event.timestamp)

    if et in {EventType.escape_risk_detected, EventType.engineering_hold} or (
        et == EventType.predictive_maintenance
        and str(payload.get("severity", "")).lower() == "critical"
    ):
        db.add(
            Alert(
                alert_id=str(uuid4()),
                timestamp=event.timestamp,
                severity="CRITICAL"
                if str(payload.get("severity", "")).lower() == "critical"
                or et == EventType.escape_risk_detected
                else "ERROR",
                alert_type=et.value,
                title=et.value.replace("_", " ").title(),
                message=text_for_event(event),
                status="open",
                tester_id=tester_id,
                site_id=site_id,
                lot_id=lot_id or event.lot_id,
                wafer_id=event.wafer_id,
                source_event_id=event.event_id,
                details=dict(payload),
            )
        )

    if et == EventType.predictive_maintenance:
        asset_id = str(payload.get("asset_id") or event.tester_id or "asset")
        asset = await db.get(MaintenanceAsset, asset_id)
        model_available = bool(payload.get("model_available", True))
        health = payload.get("health_score", payload.get("health_pct"))
        health_f = float(health) if health is not None and model_available else None
        severity = str(payload.get("severity", "unavailable"))
        status = str(
            payload.get(
                "status",
                "unavailable"
                if not model_available
                else ("warn" if severity in {"watch", "warning", "critical"} else "ok"),
            )
        )
        if asset is None:
            asset = MaintenanceAsset(
                asset_id=asset_id,
                name=str(payload.get("asset_name", asset_id)),
                health_pct=health_f,
                status=status,
                rul_days=float(payload["rul_days"]) if payload.get("rul_days") is not None else None,
                failure_probability=float(payload["failure_probability"])
                if payload.get("failure_probability") is not None
                else None,
                confidence=float(payload["confidence"]) if payload.get("confidence") is not None else None,
                severity=severity,
                recommended_action=str(payload["recommended_action"])
                if payload.get("recommended_action")
                else None,
                model_available=model_available,
                component=str(payload.get("component")) if payload.get("component") else None,
                tester_id=tester_id,
                site_id=site_id,
            )
            db.add(asset)
        else:
            asset.health_pct = health_f
            asset.status = status
            asset.severity = severity
            asset.model_available = model_available
            asset.tester_id = tester_id or asset.tester_id
            asset.site_id = site_id or asset.site_id
            if payload.get("rul_days") is not None:
                asset.rul_days = float(payload["rul_days"])
            if payload.get("failure_probability") is not None:
                asset.failure_probability = float(payload["failure_probability"])
            if payload.get("confidence") is not None:
                asset.confidence = float(payload["confidence"])
            if payload.get("recommended_action") is not None:
                asset.recommended_action = str(payload["recommended_action"])
            if payload.get("component"):
                asset.component = str(payload["component"])
            if payload.get("asset_name"):
                asset.name = str(payload["asset_name"])
            asset.updated_at = datetime.utcnow()

    if et == EventType.dynamic_limit_updated:
        limit_id = str(payload.get("limit_id") or f"lim-{event.sequence_number}")
        direction = str(payload.get("direction", "tightened"))
        change_pct = float(payload.get("change_percentage", payload.get("change_pct", 0)))
        parameter = str(payload.get("parameter", "Limit"))
        test_name = str(payload.get("test_name", parameter))
        status = str(payload.get("status", "ACTIVE"))
        row = await db.get(TestLimitRecord, limit_id)
        if row is None:
            current = float(payload.get("current_limit", 0))
            previous = float(payload.get("previous_limit", current))
            row = TestLimitRecord(
                limit_id=limit_id,
                parameter=parameter,
                test_name=test_name,
                site_id=site_id,
                tester_id=tester_id,
                lot_id=lot_id or event.lot_id,
                previous_limit=previous,
                current_limit=current,
                delta=float(payload.get("delta", current - previous)),
                change_percentage=change_pct,
                direction=direction,
                cpk=float(payload["cpk"]) if payload.get("cpk") is not None else None,
                target_cpk=float(payload.get("target_cpk", 1.33)),
                confidence=float(payload["confidence"]) if payload.get("confidence") is not None else None,
                reason=str(payload["reason"]) if payload.get("reason") is not None else None,
                status=status,
                created_at=event.timestamp,
                updated_at=event.timestamp,
            )
            db.add(row)
            if status == "ACTIVE":
                state.adjustments_today += 1
        else:
            # Authoritative service already persisted; only fill gaps from stream
            if payload.get("parameter"):
                row.parameter = parameter
            if payload.get("test_name"):
                row.test_name = test_name
            if payload.get("current_limit") is not None:
                row.current_limit = float(payload["current_limit"])
            if payload.get("previous_limit") is not None:
                row.previous_limit = float(payload["previous_limit"])
            if payload.get("delta") is not None:
                row.delta = float(payload["delta"])
            row.change_percentage = change_pct
            row.direction = direction
            if payload.get("status"):
                row.status = status
            if payload.get("cpk") is not None:
                row.cpk = float(payload["cpk"])
            if payload.get("reason") is not None:
                row.reason = str(payload["reason"])
            row.updated_at = event.timestamp

    if et == EventType.tester_status_changed and event.tester_id:
        tester = await db.get(Tester, event.tester_id)
        if tester is None:
            tester = Tester(
                tester_id=event.tester_id,
                name=str(payload.get("name", event.tester_id)),
                status=str(payload.get("status", "online")),
                site_id=event.site_id,
                health_pct=float(payload["health_pct"]) if payload.get("health_pct") is not None else None,
            )
            db.add(tester)
        else:
            tester.status = str(payload.get("status", tester.status))
            if payload.get("health_pct") is not None:
                tester.health_pct = float(payload["health_pct"])
            tester.updated_at = datetime.utcnow()

    # Materialize event-center rows for notable events (skip per-die noise unless requested)
    if materialize_floor_log and (
        not et.value.startswith("die_")
        or et
        in {
            EventType.die_reclassified,
            EventType.die_fail,
            EventType.die_retest,
            EventType.escape_risk_detected,
        }
    ):
        severity = severity_for_event(event)
        message = text_for_event(event)
        tag = tag_from_severity(severity)
        meta = dict(event.payload or {})
        existing = await db.get(FloorEventView, event.event_id)
        if existing is None:
            db.add(
                FloorEventView(
                    event_id=event.event_id,
                    event_type=et.value,
                    timestamp=event.timestamp,
                    severity=severity.value,
                    source=event.source,
                    tester_id=tester_id,
                    site_id=site_id,
                    lot_id=lot_id or event.lot_id,
                    wafer_id=event.wafer_id,
                    die_id=event.die_id,
                    message=message,
                    event_metadata=meta,
                    acknowledged=False,
                    sequence_number=event.sequence_number,
                    tag=tag,
                    text=message,
                )
            )
        else:
            existing.event_type = et.value
            existing.timestamp = event.timestamp
            existing.severity = severity.value
            existing.source = event.source
            existing.tester_id = tester_id
            existing.site_id = site_id
            existing.lot_id = lot_id or event.lot_id
            existing.wafer_id = event.wafer_id
            existing.die_id = event.die_id
            existing.message = message
            existing.event_metadata = meta
            existing.sequence_number = event.sequence_number
            existing.tag = tag
            existing.text = message

    state.updated_at = datetime.utcnow()
