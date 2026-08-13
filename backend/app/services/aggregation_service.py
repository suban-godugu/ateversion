from __future__ import annotations

from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import (
    LotRepository,
    OptimizationMetricRepository,
    PageParams,
    TesterRepository,
    TimeRange,
    WaferRepository,
)


class AggregationService:
    """Lot / tester / site / wafer yield aggregations from PostgreSQL."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.wafer_repo = WaferRepository(db)
        self.lot_repo = LotRepository(db)
        self.tester_repo = TesterRepository(db)
        self.metric_repo = OptimizationMetricRepository(db)

    def _range(self, since: datetime | None, until: datetime | None) -> TimeRange | None:
        if since is None and until is None:
            return None
        return TimeRange(since=since, until=until)

    async def wafer_yield(
        self,
        *,
        lot_id: str | None = None,
        tester_id: str | None = None,
        site_id: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> dict:
        return await self.wafer_repo.yield_aggregation(
            lot_id=lot_id,
            tester_id=tester_id,
            site_id=site_id,
            time_range=self._range(since, until),
        )

    async def lots(
        self,
        *,
        tester_id: str | None = None,
        site_id: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> dict:
        return await self.lot_repo.aggregation(
            tester_id=tester_id,
            site_id=site_id,
            time_range=self._range(since, until),
        )

    async def testers(self, *, site_id: str | None = None) -> dict:
        return await self.tester_repo.aggregation(site_id=site_id)

    async def site_rollup(
        self,
        site_id: str,
        *,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> dict:
        return {
            "site_id": site_id,
            "testers": await self.testers(site_id=site_id),
            "lots": await self.lots(site_id=site_id, since=since, until=until),
            "wafer_yield": await self.wafer_yield(site_id=site_id, since=since, until=until),
        }

    async def kpi_history(
        self,
        metric_id: str,
        *,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 100,
    ) -> list[dict]:
        rows = await self.metric_repo.history(
            metric_id,
            time_range=self._range(since, until),
            limit=limit,
        )
        if rows:
            return [
                {
                    "history_id": r.history_id,
                    "metric_id": r.metric_id,
                    "value": r.value,
                    "timestamp": r.timestamp,
                    "source": r.source,
                }
                for r in rows
            ]
        # Fallback to embedded JSON history on OptimizationMetric
        metric = await self.metric_repo.get(metric_id)
        if metric is None:
            return []
        hist = list(metric.history or [])
        points = []
        for h in hist[-limit:]:
            if isinstance(h, dict):
                points.append(
                    {
                        "history_id": None,
                        "metric_id": metric_id,
                        "value": float(h.get("v", h.get("value", 0))),
                        "timestamp": h.get("t", h.get("timestamp")),
                        "source": "embedded",
                    }
                )
        return list(reversed(points))

    async def list_wafers_page(self, **kwargs):
        return await self.wafer_repo.list_wafers(**kwargs)
