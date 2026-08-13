from __future__ import annotations

from datetime import datetime

from sqlalchemy import and_, desc, func, or_, select

from app.models.entities import Alert, AuditLog, TestEvent, TelemetryEvent
from app.repositories.base import FilterSpec, Page, PageParams, Repository, SortParams, TimeRange


class TestEventRepository(Repository[TestEvent]):
    model = TestEvent

    async def list_events(
        self,
        *,
        q: str | None = None,
        tester_id: str | None = None,
        site_id: str | None = None,
        lot_id: str | None = None,
        wafer_id: str | None = None,
        event_type: str | None = None,
        severity: list[str] | None = None,
        acknowledged: bool | None = None,
        time_range: TimeRange | None = None,
        sort: SortParams | None = None,
        page: PageParams | None = None,
    ) -> Page[TestEvent]:
        page = (page or PageParams()).clamp()
        stmt = select(TestEvent)
        clauses = []
        if tester_id:
            clauses.append(TestEvent.tester_id == tester_id)
        if site_id:
            clauses.append(TestEvent.site_id == site_id)
        if lot_id:
            clauses.append(TestEvent.lot_id == lot_id)
        if wafer_id:
            clauses.append(TestEvent.wafer_id == wafer_id)
        if event_type:
            clauses.append(TestEvent.event_type == event_type)
        if acknowledged is not None:
            clauses.append(TestEvent.acknowledged.is_(acknowledged))
        if severity:
            clauses.append(TestEvent.severity.in_(severity))
        if time_range and time_range.since:
            clauses.append(TestEvent.timestamp >= time_range.since)
        if time_range and time_range.until:
            clauses.append(TestEvent.timestamp <= time_range.until)
        if q:
            pattern = f"%{q.strip()}%"
            clauses.append(
                or_(
                    TestEvent.message.ilike(pattern),
                    TestEvent.text.ilike(pattern),
                    TestEvent.event_type.ilike(pattern),
                    TestEvent.tester_id.ilike(pattern),
                    TestEvent.lot_id.ilike(pattern),
                    TestEvent.wafer_id.ilike(pattern),
                    TestEvent.die_id.ilike(pattern),
                    TestEvent.source.ilike(pattern),
                )
            )
        where = and_(*clauses) if clauses else True
        total = int(
            (await self.session.execute(select(func.count()).select_from(TestEvent).where(where))).scalar_one()
        )
        unack = int(
            (
                await self.session.execute(
                    select(func.count())
                    .select_from(TestEvent)
                    .where(and_(where, TestEvent.acknowledged.is_(False)))
                )
            ).scalar_one()
        )
        sort = sort or SortParams(field="sequence_number", direction="desc")
        col = getattr(TestEvent, sort.field, TestEvent.sequence_number)
        order = desc(col) if sort.direction != "asc" else col.asc()
        rows = (
            await self.session.execute(
                select(TestEvent).where(where).order_by(order, desc(TestEvent.timestamp)).offset(page.offset).limit(page.limit)
            )
        ).scalars().all()
        page_out = Page(items=list(rows), total=total, limit=page.limit, offset=page.offset)
        # stash unack on page via monkey attribute for service
        page_out.unacknowledged = unack  # type: ignore[attr-defined]
        return page_out

    async def acknowledge(self, event_id: str, *, actor: str, comment: str | None = None) -> TestEvent | None:
        row = await self.get(event_id)
        if row is None:
            return None
        row.acknowledged = True
        row.acknowledged_by = actor
        row.acknowledged_at = datetime.utcnow()
        meta = dict(row.event_metadata or {})
        if comment:
            meta["ack_comment"] = comment
        row.event_metadata = meta
        await self.session.flush()
        return row


class TelemetryEventRepository(Repository[TelemetryEvent]):
    model = TelemetryEvent

    async def list_events(
        self,
        *,
        event_type: str | None = None,
        tester_id: str | None = None,
        lot_id: str | None = None,
        wafer_id: str | None = None,
        time_range: TimeRange | None = None,
        page: PageParams | None = None,
    ) -> Page[TelemetryEvent]:
        return await self.paginate(
            filters=FilterSpec(
                equals={
                    "event_type": event_type,
                    "tester_id": tester_id,
                    "lot_id": lot_id,
                    "wafer_id": wafer_id,
                },
                time_field="timestamp",
                time_range=time_range,
            ),
            sort=SortParams(field="sequence_number", direction="desc"),
            page=page,
            default_sort_field="timestamp",
        )


class AlertRepository(Repository[Alert]):
    model = Alert

    async def list_alerts(
        self,
        *,
        severity: list[str] | None = None,
        status: str | None = None,
        tester_id: str | None = None,
        time_range: TimeRange | None = None,
        page: PageParams | None = None,
    ) -> Page[Alert]:
        return await self.paginate(
            filters=FilterSpec(
                equals={"status": status, "tester_id": tester_id},
                any_of={"severity": severity or []},
                time_field="timestamp",
                time_range=time_range,
            ),
            sort=SortParams(field="timestamp", direction="desc"),
            page=page,
        )


class AuditLogRepository(Repository[AuditLog]):
    model = AuditLog

    async def list_audits(
        self,
        *,
        entity_type: str | None = None,
        entity_id: str | None = None,
        actor: str | None = None,
        time_range: TimeRange | None = None,
        page: PageParams | None = None,
    ) -> Page[AuditLog]:
        return await self.paginate(
            filters=FilterSpec(
                equals={"entity_type": entity_type, "entity_id": entity_id, "actor": actor},
                time_field="timestamp",
                time_range=time_range,
            ),
            sort=SortParams(field="timestamp", direction="desc"),
            page=page,
        )

    async def write(
        self,
        *,
        actor: str,
        action: str,
        entity_type: str,
        entity_id: str,
        detail: str = "",
        before: dict | None = None,
        after: dict | None = None,
        tester_id: str | None = None,
        lot_id: str | None = None,
        wafer_id: str | None = None,
        site_id: str | None = None,
    ) -> AuditLog:
        from uuid import uuid4

        row = AuditLog(
            audit_id=str(uuid4()),
            actor=actor,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            detail=detail,
            before_json=before,
            after_json=after,
            tester_id=tester_id,
            lot_id=lot_id,
            wafer_id=wafer_id,
            site_id=site_id,
        )
        self.session.add(row)
        await self.session.flush()
        return row
