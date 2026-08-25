from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import FloorEventView, KpiMetric, Lot, Tester, Wafer
from app.schemas.api import (
    KpiDetailOut,
    KpiHistoryOut,
    KpiHistoryPoint,
    KpiOut,
    KpisListOut,
)

Trend = Literal["up", "down", "flat"]
Status = Literal["on_track", "at_risk", "below_target", "exceeds_target"]

# Event type → KPI ids that should refresh (server-side mapping only)
EVENT_KPI_MAP: dict[str, list[str]] = {
    "yield_updated": ["yield_improvement", "false_failure_reduction", "escape_prevention"],
    "test_time_updated": ["test_time_reduction"],
    "pattern_optimization": [
        "vector_memory_optimization",
        "pattern_count_reduction",
        "test_time_reduction",
    ],
    "optimization_completed": [
        "false_failure_reduction",
        "yield_improvement",
        "retest_reduction",
        "escape_prevention",
        "test_time_reduction",
        "vector_memory_optimization",
        "pattern_count_reduction",
        "m_bist_shmoo",
    ],
}


def compute_improvement(value: float, previous_value: float) -> float:
    return round(value - previous_value, 4)


def compute_trend(value: float, previous_value: float, epsilon: float = 1e-6) -> Trend:
    delta = value - previous_value
    if abs(delta) <= epsilon:
        return "flat"
    return "up" if delta > 0 else "down"


def compute_status(value: float, baseline: float, target: float) -> Status:
    # Higher-is-better KPIs (all current optimization KPIs)
    if value >= target:
        return "exceeds_target"
    if value >= baseline:
        return "on_track"
    if value >= baseline * 0.9:
        return "at_risk"
    return "below_target"


def _parse_ts(raw: Any, fallback: datetime) -> datetime:
    if not raw:
        return fallback
    try:
        text = str(raw).replace("Z", "")
        return datetime.fromisoformat(text)
    except Exception:
        return fallback


def _history_from_metric(metric: KpiMetric) -> list[KpiHistoryPoint]:
    raw = metric.history or metric.series or []
    points: list[KpiHistoryPoint] = []
    for i, item in enumerate(raw):
        if isinstance(item, dict):
            points.append(
                KpiHistoryPoint(
                    timestamp=_parse_ts(item.get("timestamp"), metric.updated_at),
                    value=float(item["value"]),
                )
            )
        else:
            points.append(KpiHistoryPoint(timestamp=metric.updated_at, value=float(item), index=i))
    return points[-48:]


def to_kpi_out(metric: KpiMetric) -> KpiOut:
    history = _history_from_metric(metric)
    return KpiOut(
        id=metric.key,
        name=metric.title,
        value=metric.value,
        unit=metric.unit,
        baseline=metric.baseline,
        target=metric.target,
        previous_value=metric.previous_value,
        improvement=metric.improvement,
        trend=metric.trend if metric.trend in ("up", "down", "flat") else "flat",  # type: ignore[arg-type]
        status=metric.status if metric.status in ("on_track", "at_risk", "below_target", "exceeds_target") else "on_track",  # type: ignore[arg-type]
        timestamp=metric.updated_at,
        history=history,
        description=metric.description,
        accent=metric.accent,
    )


async def update_kpi_value(
    db: AsyncSession,
    kpi_id: str,
    new_value: float,
    *,
    at: datetime | None = None,
) -> KpiMetric | None:
    """Authoritative KPI update — previous/improvement/trend/status/history computed in Python."""
    metric = await db.get(KpiMetric, kpi_id)
    if metric is None:
        return None
    ts = at or datetime.utcnow()
    previous = float(metric.value)
    value = float(new_value)
    metric.previous_value = previous
    metric.value = value
    metric.improvement = compute_improvement(value, previous)
    metric.trend = compute_trend(value, previous)
    metric.status = compute_status(value, float(metric.baseline), float(metric.target))
    metric.updated_at = ts

    history = list(metric.history or [])
    history.append({"timestamp": ts.isoformat(), "value": value})
    metric.history = history[-48:]
    # keep legacy series for dashboard summary compatibility
    series = list(metric.series or [])
    series.append(value)
    metric.series = series[-48:]
    return metric


async def apply_shmoo_results_to_kpis(
    db: AsyncSession,
    results: dict[str, Any],
    *,
    at: datetime | None = None,
) -> list[str]:
    """Update SHMOO parent CV% and embedded capability metrics from ML results."""
    from app.ingestion.seed import ensure_missing_kpi_defs

    await ensure_missing_kpi_defs(db)

    updated: list[str] = []
    n_pass = float(results.get("n_pass") or 0)
    n_fail = float(results.get("n_fail") or 0)
    total = n_pass + n_fail
    pass_rate = (n_pass / total * 100.0) if total > 0 else 0.0
    fail_rate = (n_fail / total * 100.0) if total > 0 else 0.0
    cv_pct = float(results.get("cv_accuracy") or 0) * 100.0
    r2_pct = float(results.get("boundary_r2") or 0) * 100.0

    mapping = {
        "m_bist_shmoo": cv_pct,
        "shmoo_yield_analysis": pass_rate,
        "shmoo_debugging": fail_rate,
        "shmoo_binning": pass_rate,  # proxy until multi-device binning API
        "shmoo_characterization": r2_pct,
    }
    for key, value in mapping.items():
        m = await update_kpi_value(db, key, round(value, 4), at=at)
        if m:
            updated.append(m.key)
    return updated


async def apply_kpi_updates_from_event(
    db: AsyncSession,
    event_type: str,
    payload: dict[str, Any],
    *,
    at: datetime | None = None,
) -> list[str]:
    updated: list[str] = []
    explicit = payload.get("kpi_updates") or {}
    if isinstance(explicit, dict) and explicit:
        for key, value in explicit.items():
            m = await update_kpi_value(db, str(key), float(value), at=at)
            if m:
                updated.append(m.key)
        return updated

    # Derived updates from telemetry payloads (still server-side, no client math)
    if event_type == "test_time_updated" and "reduction_pct" in payload:
        m = await update_kpi_value(db, "test_time_reduction", float(payload["reduction_pct"]), at=at)
        if m:
            updated.append(m.key)
    if event_type == "yield_updated" and "yield_improvement_pts" in payload:
        m = await update_kpi_value(db, "yield_improvement", float(payload["yield_improvement_pts"]), at=at)
        if m:
            updated.append(m.key)
    return updated


async def list_kpis(db: AsyncSession) -> KpisListOut:
    from app.ingestion.seed import ensure_missing_kpi_defs

    await ensure_missing_kpi_defs(db)
    rows = (await db.execute(select(KpiMetric).order_by(KpiMetric.title))).scalars().all()
    return KpisListOut(kpis=[to_kpi_out(m) for m in rows])


async def get_kpi(db: AsyncSession, kpi_id: str) -> KpiDetailOut | None:
    metric = await db.get(KpiMetric, kpi_id)
    if metric is None:
        return None
    base = to_kpi_out(metric)
    lots = int((await db.scalar(select(func.count()).select_from(Lot))) or 0)
    wafers = int((await db.scalar(select(func.count()).select_from(Wafer))) or 0)
    testers = int((await db.scalar(select(func.count()).select_from(Tester))) or 0)
    sites = int(
        (await db.scalar(select(func.count(func.distinct(Tester.site_id))).where(Tester.site_id.is_not(None))))
        or 0
    )
    events = (
        await db.execute(select(FloorEventView).order_by(desc(FloorEventView.timestamp)).limit(8))
    ).scalars().all()
    from app.schemas.api import EventLogItem

    recent = [
        EventLogItem(
            event_id=e.event_id,
            event_type=e.event_type,
            timestamp=e.timestamp,
            tag=e.tag if e.tag in ("pass", "warn", "info") else "info",  # type: ignore[arg-type]
            text=e.text,
            lot_id=e.lot_id,
            wafer_id=e.wafer_id,
            tester_id=e.tester_id,
        )
        for e in events
    ]
    return KpiDetailOut(
        **base.model_dump(),
        lots=lots,
        wafers=wafers,
        testers=testers,
        sites=sites,
        recent_events=recent,
    )


async def get_kpi_history(db: AsyncSession, kpi_id: str, limit: int = 48) -> KpiHistoryOut | None:
    metric = await db.get(KpiMetric, kpi_id)
    if metric is None:
        return None
    points = _history_from_metric(metric)[-limit:]
    return KpiHistoryOut(id=metric.key, name=metric.title, unit=metric.unit, history=points)
