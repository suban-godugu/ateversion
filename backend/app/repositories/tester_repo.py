from __future__ import annotations

from sqlalchemy import func, select

from app.models.entities import PredictiveMaintenance, Tester, TesterSite
from app.repositories.base import FilterSpec, Page, PageParams, Repository, SortParams


class TesterSiteRepository(Repository[TesterSite]):
    model = TesterSite


class TesterRepository(Repository[Tester]):
    model = Tester

    async def list_testers(
        self,
        *,
        site_id: str | None = None,
        status: str | None = None,
        page: PageParams | None = None,
    ) -> Page[Tester]:
        return await self.paginate(
            filters=FilterSpec(equals={"site_id": site_id, "status": status}, time_field=None),
            sort=SortParams(field="tester_id", direction="asc"),
            page=page or PageParams(limit=100, offset=0),
            default_sort_field="tester_id",
        )

    async def aggregation(self, *, site_id: str | None = None) -> dict:
        stmt = select(
            func.count(Tester.tester_id),
            func.coalesce(func.avg(Tester.health_pct), 0.0),
        )
        if site_id:
            stmt = stmt.where(Tester.site_id == site_id)
        row = (await self.session.execute(stmt)).one()
        online_stmt = select(func.count()).select_from(Tester).where(Tester.status == "online")
        if site_id:
            online_stmt = online_stmt.where(Tester.site_id == site_id)
        online = (await self.session.execute(online_stmt)).scalar_one()
        return {
            "tester_count": int(row[0] or 0),
            "online_count": int(online or 0),
            "avg_health_pct": float(row[1] or 0.0),
        }


class PredictiveMaintenanceRepository(Repository[PredictiveMaintenance]):
    model = PredictiveMaintenance

    async def list_assets(
        self,
        *,
        tester_id: str | None = None,
        site_id: str | None = None,
        severity: list[str] | None = None,
        page: PageParams | None = None,
    ) -> Page[PredictiveMaintenance]:
        return await self.paginate(
            filters=FilterSpec(
                equals={"tester_id": tester_id, "site_id": site_id},
                any_of={"severity": severity or []},
                time_field="updated_at",
            ),
            sort=SortParams(field="updated_at", direction="desc"),
            page=page,
            default_sort_field="updated_at",
        )
