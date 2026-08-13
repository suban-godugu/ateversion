from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import PageParams, SortParams, TestEventRepository, TimeRange
from app.services.test_events.models import (
    AcknowledgeRequest,
    EventFilterParams,
    EventSeverity,
    TestEvent,
    TestEventsListOut,
)
from app.services.unit_of_work import transactional_session


class TestEventsService:
    """Event center service — SQL lives in TestEventRepository only."""

    def _to_model(self, row) -> TestEvent:
        severity = (
            EventSeverity(row.severity)
            if row.severity in EventSeverity._value2member_map_
            else EventSeverity.INFO
        )
        return TestEvent(
            event_id=row.event_id,
            timestamp=row.timestamp,
            severity=severity,
            event_type=row.event_type,
            source=row.source or "ingestion",
            tester_id=row.tester_id,
            site_id=row.site_id,
            lot_id=row.lot_id,
            wafer_id=row.wafer_id,
            die_id=row.die_id,
            message=row.message or row.text or "",
            metadata=dict(row.event_metadata or {}),
            acknowledged=bool(row.acknowledged),
            acknowledged_by=row.acknowledged_by,
            acknowledged_at=row.acknowledged_at,
            sequence_number=int(row.sequence_number or 0),
        )

    async def list_events(self, db: AsyncSession, params: EventFilterParams) -> TestEventsListOut:
        repo = TestEventRepository(db)
        page = await repo.list_events(
            q=params.q,
            tester_id=params.tester_id,
            site_id=params.site_id,
            lot_id=params.lot_id,
            wafer_id=params.wafer_id,
            event_type=params.event_type,
            severity=[s.value for s in params.severity] if params.severity else None,
            acknowledged=params.acknowledged,
            time_range=TimeRange(since=params.since, until=params.until),
            sort=SortParams(field="sequence_number", direction="desc"),
            page=PageParams(limit=params.limit, offset=params.offset),
        )
        unack = getattr(page, "unacknowledged", page.total)
        return TestEventsListOut(
            total=page.total,
            unacknowledged=int(unack),
            items=[self._to_model(r) for r in page.items],
        )

    async def get_event(self, db: AsyncSession, event_id: str) -> TestEvent:
        row = await TestEventRepository(db).get(event_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Event not found")
        return self._to_model(row)

    async def acknowledge(
        self, db: AsyncSession, event_id: str, body: AcknowledgeRequest
    ) -> TestEvent:
        async with transactional_session(db):
            repo = TestEventRepository(db)
            row = await repo.acknowledge(event_id, actor=body.actor, comment=body.comment)
            if row is None:
                raise HTTPException(status_code=404, detail="Event not found")
            return self._to_model(row)

    async def filter_options(self, db: AsyncSession) -> dict[str, list[str]]:
        from sqlalchemy import select

        from app.models.entities import TestEvent as TestEventRow
        from app.services.test_events.models import EventSeverity

        async def distinct(col):
            rows = (
                await db.execute(select(col).where(col.is_not(None)).distinct().order_by(col))
            ).all()
            return [str(r[0]) for r in rows if r[0]]

        return {
            "testers": await distinct(TestEventRow.tester_id),
            "sites": await distinct(TestEventRow.site_id),
            "lots": await distinct(TestEventRow.lot_id),
            "wafers": await distinct(TestEventRow.wafer_id),
            "severities": [s.value for s in EventSeverity],
            "event_types": await distinct(TestEventRow.event_type),
        }
