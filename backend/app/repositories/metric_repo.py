from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import OptimizationMetric, OptimizationMetricHistory
from app.repositories.base import FilterSpec, Page, PageParams, Repository, SortParams, TimeRange


class OptimizationMetricRepository(Repository[OptimizationMetric]):
    model = OptimizationMetric

    async def list_metrics(
        self,
        *,
        status: str | None = None,
        sort: SortParams | None = None,
        page: PageParams | None = None,
    ) -> Page[OptimizationMetric]:
        return await self.paginate(
            filters=FilterSpec(equals={"status": status}, time_field=None),
            sort=sort or SortParams(field="title", direction="asc"),
            page=page or PageParams(limit=100, offset=0),
            default_sort_field="title",
        )

    async def history(
        self,
        metric_id: str,
        *,
        time_range: TimeRange | None = None,
        limit: int = 100,
    ) -> list[OptimizationMetricHistory]:
        stmt = select(OptimizationMetricHistory).where(
            OptimizationMetricHistory.metric_id == metric_id
        )
        if time_range and time_range.since:
            stmt = stmt.where(OptimizationMetricHistory.timestamp >= time_range.since)
        if time_range and time_range.until:
            stmt = stmt.where(OptimizationMetricHistory.timestamp <= time_range.until)
        stmt = stmt.order_by(desc(OptimizationMetricHistory.timestamp)).limit(limit)
        return list((await self.session.execute(stmt)).scalars().all())

    async def append_history(
        self,
        metric_id: str,
        value: float,
        *,
        timestamp: datetime | None = None,
        source: str = "system",
        meta: dict | None = None,
    ) -> OptimizationMetricHistory:
        row = OptimizationMetricHistory(
            history_id=str(uuid4()),
            metric_id=metric_id,
            value=value,
            timestamp=timestamp or datetime.utcnow(),
            source=source,
            meta=meta or {},
        )
        self.session.add(row)
        await self.session.flush()
        return row
