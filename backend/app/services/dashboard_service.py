from __future__ import annotations

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import (
    DashboardState,
    Die,
    FloorEventView,
    KpiMetric,
    MaintenanceAsset,
    Tester,
    Wafer,
)
from app.schemas.api import (
    BinCounts,
    DashboardSummary,
    DieOut,
    EventLogItem,
    HeaderStats,
    KpiCard,
    KpisOut,
    MaintenanceAssetOut,
    MaintenanceOut,
    TestLimitOut,
    TestLimitsOut,
    TesterOut,
    WaferDetail,
    WaferListItem,
)
from app.services.projections import ensure_dashboard_state


async def get_header(db: AsyncSession) -> HeaderStats:
    state = await ensure_dashboard_state(db)
    return HeaderStats(
        lots_in_test=state.lots_in_test,
        test_time_saved_hours=state.test_time_saved_hours,
        overall_yield_pct=state.overall_yield_pct,
    )


def _wafer_detail(wafer: Wafer) -> WaferDetail:
    return WaferDetail(
        wafer_id=wafer.wafer_id,
        lot_id=wafer.lot_id,
        status=wafer.status,
        yield_pct=wafer.yield_pct,
        total_dies=wafer.total_dies,
        tested_dies=wafer.tested_dies,
        caption=wafer.caption or f"Live wafer map · Lot {wafer.lot_id}",
        pass_count=wafer.pass_count,
        fail_count=wafer.fail_count,
        retest_count=wafer.retest_count,
        reclass_count=wafer.reclass_count,
        bin_counts=BinCounts(
            **{
                "pass": wafer.pass_count,
                "retest": wafer.retest_count,
                "fail": wafer.fail_count,
                "reclass": wafer.reclass_count,
            }
        ),
    )


async def list_wafers(db: AsyncSession) -> list[WaferListItem]:
    rows = (await db.execute(select(Wafer).order_by(desc(Wafer.updated_at)))).scalars().all()
    return [
        WaferListItem(
            wafer_id=w.wafer_id,
            lot_id=w.lot_id,
            status=w.status,
            yield_pct=w.yield_pct,
            total_dies=w.total_dies,
            tested_dies=w.tested_dies,
        )
        for w in rows
    ]


async def get_wafer(db: AsyncSession, wafer_id: str) -> WaferDetail | None:
    wafer = await db.get(Wafer, wafer_id)
    if wafer is None:
        return None
    return _wafer_detail(wafer)


async def get_dies(db: AsyncSession, wafer_id: str) -> list[DieOut]:
    rows = (await db.execute(select(Die).where(Die.wafer_id == wafer_id).order_by(Die.y, Die.x))).scalars().all()
    out: list[DieOut] = []
    for d in rows:
        result = d.bin if d.bin in ("pass", "retest", "fail", "reclass", "untested") else "untested"
        out.append(
            DieOut(
                die_id=d.die_id,
                wafer_id=d.wafer_id,
                x=d.x,
                y=d.y,
                row=d.y,
                column=d.x,
                result=result,  # type: ignore[arg-type]
                bin=result,  # type: ignore[arg-type]
                fail_code=d.fail_code,
                test_time_ms=d.test_time_ms,
                confidence=d.confidence,
                timestamp=d.tested_at or d.updated_at,
            )
        )
    return out


async def get_kpis(db: AsyncSession) -> KpisOut:
    rows = (await db.execute(select(KpiMetric).order_by(KpiMetric.title))).scalars().all()
    cards: list[KpiCard] = []
    for m in rows:
        series_vals: list[float] = []
        for x in m.series or []:
            if isinstance(x, dict):
                series_vals.append(float(x.get("value", 0)))
            else:
                series_vals.append(float(x))
        trend = m.trend if m.trend in ("up", "down", "flat") else "flat"
        cards.append(
            KpiCard(
                key=m.key,
                title=m.title,
                value=m.value,
                unit=m.unit,
                description=m.description,
                accent=m.accent,
                trend=trend,  # type: ignore[arg-type]
                series=series_vals,
                baseline=float(m.baseline or 0),
                target=float(m.target or 0),
                previous_value=float(m.previous_value or 0),
                improvement=float(m.improvement or 0),
                status=m.status or "on_track",
                timestamp=m.updated_at,
            )
        )
    return KpisOut(cards=cards)


async def get_maintenance(db: AsyncSession) -> MaintenanceOut:
    from app.ml.predictive_maintenance.predictor import get_model

    rows = (await db.execute(select(MaintenanceAsset).order_by(MaintenanceAsset.health_pct.nulls_last()))).scalars().all()
    model_ok = get_model().ensure_ready()
    assets: list[MaintenanceAssetOut] = []
    for a in rows:
        sev = a.severity if a.severity in ("healthy", "watch", "warning", "critical", "offline", "unavailable") else "unavailable"
        available = bool(a.model_available) and model_ok
        if not available:
            sev = "unavailable"
        status = "unavailable" if not available else ("warn" if sev in ("watch", "warning", "critical") else "ok")
        assets.append(
            MaintenanceAssetOut(
                asset_id=a.asset_id,
                name=a.name,
                health_pct=a.health_pct if available else None,
                status=status,  # type: ignore[arg-type]
                rul_days=a.rul_days if available else None,
                tester_id=a.tester_id,
                component=a.component,
                failure_probability=a.failure_probability if available else None,
                confidence=a.confidence if available else None,
                severity=sev,  # type: ignore[arg-type]
                recommended_action=a.recommended_action if available else None,
                model_available=available,
                message=None if available else "Prediction unavailable",
                updated_at=a.updated_at,
            )
        )
    flagged = sum(1 for a in assets if a.severity in ("warning", "critical"))
    return MaintenanceOut(flagged_count=flagged, model_available=model_ok, assets=assets)


async def get_test_limits(db: AsyncSession) -> TestLimitsOut:
    from app.services.test_limits.service import TestLimitsService

    listed = await TestLimitsService().list_limits(db)
    items = [
        TestLimitOut(
            limit_id=i.limit_id,
            parameter=i.parameter,
            test_name=i.test_name,
            name=f"{i.parameter} · {i.test_name}",
            site_id=i.site_id,
            tester_id=i.tester_id,
            lot_id=i.lot_id,
            previous_limit=i.previous_limit,
            current_limit=i.current_limit,
            delta=i.delta,
            change_percentage=i.change_percentage,
            change_pct=i.change_percentage,
            change_label=i.change_label or "",
            direction=i.direction.value,  # type: ignore[arg-type]
            cpk=i.cpk,
            target_cpk=i.target_cpk,
            confidence=i.confidence,
            reason=i.reason,
            status=i.status.value,  # type: ignore[arg-type]
            created_at=i.created_at,
            updated_at=i.updated_at,
        )
        for i in listed.items
    ]
    return TestLimitsOut(adjustments_today=listed.adjustments_today, items=items)


async def get_events(db: AsyncSession, limit: int = 50) -> list[EventLogItem]:
    rows = (
        await db.execute(
            select(FloorEventView)
            .order_by(desc(FloorEventView.sequence_number), desc(FloorEventView.timestamp))
            .limit(limit)
        )
    ).scalars().all()
    items: list[EventLogItem] = []
    for r in rows:
        tag = r.tag if r.tag in ("pass", "warn", "info") else "info"
        if r.severity == "PASS":
            tag = "pass"
        elif r.severity in ("WARN", "ERROR", "CRITICAL"):
            tag = "warn"
        items.append(
            EventLogItem(
                event_id=r.event_id,
                event_type=r.event_type,
                timestamp=r.timestamp,
                tag=tag,  # type: ignore[arg-type]
                text=r.message or r.text,
                lot_id=r.lot_id,
                wafer_id=r.wafer_id,
                tester_id=r.tester_id,
            )
        )
    return items


async def get_testers(db: AsyncSession) -> list[TesterOut]:
    rows = (await db.execute(select(Tester).order_by(Tester.tester_id))).scalars().all()
    return [
        TesterOut(
            tester_id=t.tester_id,
            name=t.name,
            status=t.status,
            site_id=t.site_id,
            health_pct=t.health_pct,
        )
        for t in rows
    ]


async def get_summary(db: AsyncSession) -> DashboardSummary:
    state = await ensure_dashboard_state(db)
    header = await get_header(db)
    active = None
    if state.active_wafer_id:
        active = await get_wafer(db, state.active_wafer_id)
    if active is None:
        wafers = await list_wafers(db)
        if wafers:
            active = await get_wafer(db, wafers[0].wafer_id)
    kpis = await get_kpis(db)
    return DashboardSummary(
        header=header,
        active_wafer=active,
        kpis=kpis.cards,
        maintenance=await get_maintenance(db),
        test_limits=await get_test_limits(db),
        recent_events=await get_events(db, limit=12),
    )
