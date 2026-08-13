from __future__ import annotations

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import Die, DieTestResult, Lot, Wafer, WaferMetric
from app.repositories.base import FilterSpec, Page, PageParams, Repository, SortParams, TimeRange


class WaferRepository(Repository[Wafer]):
    model = Wafer

    async def list_wafers(
        self,
        *,
        lot_id: str | None = None,
        tester_id: str | None = None,
        site_id: str | None = None,
        status: str | None = None,
        sort: SortParams | None = None,
        page: PageParams | None = None,
    ) -> Page[Wafer]:
        return await self.paginate(
            filters=FilterSpec(
                equals={
                    "lot_id": lot_id,
                    "tester_id": tester_id,
                    "site_id": site_id,
                    "status": status,
                }
            ),
            sort=sort or SortParams(field="updated_at", direction="desc"),
            page=page,
            default_sort_field="updated_at",
        )

    async def dies_for_wafer(self, wafer_id: str) -> list[Die]:
        rows = (
            await self.session.execute(select(Die).where(Die.wafer_id == wafer_id).order_by(Die.y, Die.x))
        ).scalars().all()
        return list(rows)

    async def yield_aggregation(
        self,
        *,
        lot_id: str | None = None,
        tester_id: str | None = None,
        site_id: str | None = None,
        time_range: TimeRange | None = None,
    ) -> dict:
        stmt = select(
            func.count(Wafer.wafer_id),
            func.coalesce(func.avg(Wafer.yield_pct), 0.0),
            func.coalesce(func.sum(Wafer.pass_count), 0),
            func.coalesce(func.sum(Wafer.fail_count), 0),
            func.coalesce(func.sum(Wafer.tested_dies), 0),
            func.coalesce(func.sum(Wafer.total_dies), 0),
        )
        if lot_id:
            stmt = stmt.where(Wafer.lot_id == lot_id)
        if tester_id:
            stmt = stmt.where(Wafer.tester_id == tester_id)
        if site_id:
            stmt = stmt.where(Wafer.site_id == site_id)
        if time_range and time_range.since:
            stmt = stmt.where(Wafer.updated_at >= time_range.since)
        if time_range and time_range.until:
            stmt = stmt.where(Wafer.updated_at <= time_range.until)
        row = (await self.session.execute(stmt)).one()
        return {
            "wafer_count": int(row[0] or 0),
            "avg_yield_pct": float(row[1] or 0.0),
            "pass_count": int(row[2] or 0),
            "fail_count": int(row[3] or 0),
            "tested_dies": int(row[4] or 0),
            "total_dies": int(row[5] or 0),
        }

    async def metric_history(
        self,
        wafer_id: str,
        *,
        metric_key: str | None = None,
        time_range: TimeRange | None = None,
        limit: int = 100,
    ) -> list[WaferMetric]:
        stmt = select(WaferMetric).where(WaferMetric.wafer_id == wafer_id)
        if metric_key:
            stmt = stmt.where(WaferMetric.metric_key == metric_key)
        if time_range and time_range.since:
            stmt = stmt.where(WaferMetric.timestamp >= time_range.since)
        if time_range and time_range.until:
            stmt = stmt.where(WaferMetric.timestamp <= time_range.until)
        stmt = stmt.order_by(desc(WaferMetric.timestamp)).limit(limit)
        return list((await self.session.execute(stmt)).scalars().all())


class LotRepository(Repository[Lot]):
    model = Lot

    async def list_lots(
        self,
        *,
        tester_id: str | None = None,
        site_id: str | None = None,
        status: str | None = None,
        time_range: TimeRange | None = None,
        sort: SortParams | None = None,
        page: PageParams | None = None,
    ) -> Page[Lot]:
        return await self.paginate(
            filters=FilterSpec(
                equals={"tester_id": tester_id, "site_id": site_id, "status": status},
                time_field="started_at",
                time_range=time_range,
            ),
            sort=sort or SortParams(field="started_at", direction="desc"),
            page=page,
            default_sort_field="started_at",
        )

    async def aggregation(
        self,
        *,
        tester_id: str | None = None,
        site_id: str | None = None,
        time_range: TimeRange | None = None,
    ) -> dict:
        stmt = select(
            func.count(Lot.lot_id),
            func.coalesce(func.avg(Lot.overall_yield_pct), 0.0),
            func.coalesce(func.sum(Lot.test_time_saved_hours), 0.0),
        )
        if tester_id:
            stmt = stmt.where(Lot.tester_id == tester_id)
        if site_id:
            stmt = stmt.where(Lot.site_id == site_id)
        if time_range and time_range.since:
            stmt = stmt.where(Lot.started_at >= time_range.since)
        if time_range and time_range.until:
            stmt = stmt.where(Lot.started_at <= time_range.until)
        row = (await self.session.execute(stmt)).one()
        active_stmt = select(func.count()).select_from(Lot).where(Lot.status == "active")
        if tester_id:
            active_stmt = active_stmt.where(Lot.tester_id == tester_id)
        if site_id:
            active_stmt = active_stmt.where(Lot.site_id == site_id)
        active = (await self.session.execute(active_stmt)).scalar_one()
        return {
            "lot_count": int(row[0] or 0),
            "active_lots": int(active or 0),
            "avg_yield_pct": float(row[1] or 0.0),
            "test_time_saved_hours": float(row[2] or 0.0),
        }


class DieTestResultRepository(Repository[DieTestResult]):
    model = DieTestResult

    async def list_results(
        self,
        *,
        wafer_id: str | None = None,
        lot_id: str | None = None,
        tester_id: str | None = None,
        time_range: TimeRange | None = None,
        page: PageParams | None = None,
    ) -> Page[DieTestResult]:
        return await self.paginate(
            filters=FilterSpec(
                equals={"wafer_id": wafer_id, "lot_id": lot_id, "tester_id": tester_id},
                time_field="timestamp",
                time_range=time_range,
            ),
            sort=SortParams(field="timestamp", direction="desc"),
            page=page,
        )
