from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthUser, require_permissions
from app.core.database import get_db
from app.core.rbac import Permission
from app.repositories.event_repo import AuditLogRepository
from app.services.test_events.models import (
    AcknowledgeRequest,
    EventFilterParams,
    EventSeverity,
    TestEvent,
    TestEventsListOut,
)
from app.services.test_events.service import TestEventsService

router = APIRouter(tags=["events"])
_svc = TestEventsService()


@router.get("/events", response_model=TestEventsListOut)
async def list_events(
    q: str | None = Query(None, description="Search message, ids, type"),
    tester_id: str | None = None,
    site_id: str | None = None,
    lot_id: str | None = None,
    wafer_id: str | None = None,
    severity: list[EventSeverity] | None = Query(None),
    event_type: str | None = None,
    acknowledged: bool | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    _: AuthUser = Depends(require_permissions(Permission.READ_EVENTS)),
) -> TestEventsListOut:
    params = EventFilterParams(
        q=q,
        tester_id=tester_id,
        site_id=site_id,
        lot_id=lot_id,
        wafer_id=wafer_id,
        severity=severity,
        event_type=event_type,
        acknowledged=acknowledged,
        since=since,
        until=until,
        limit=limit,
        offset=offset,
    )
    return await _svc.list_events(db, params)


@router.get("/events/filters", response_model=dict)
async def event_filter_options(
    db: AsyncSession = Depends(get_db),
    _: AuthUser = Depends(require_permissions(Permission.READ_EVENTS)),
) -> dict:
    return await _svc.filter_options(db)


@router.get("/events/{event_id}", response_model=TestEvent)
async def get_event(
    event_id: str,
    db: AsyncSession = Depends(get_db),
    _: AuthUser = Depends(require_permissions(Permission.READ_EVENTS)),
) -> TestEvent:
    return await _svc.get_event(db, event_id)


@router.post("/events/{event_id}/acknowledge", response_model=TestEvent)
async def acknowledge_event(
    event_id: str,
    body: AcknowledgeRequest,
    db: AsyncSession = Depends(get_db),
    user: AuthUser = Depends(require_permissions(Permission.ACK_EVENTS)),
) -> TestEvent:
    body.actor = user.username
    result = await _svc.acknowledge(db, event_id, body)
    await AuditLogRepository(db).write(
        actor=user.username,
        action="acknowledge_event",
        entity_type="test_event",
        entity_id=event_id,
        detail=body.comment or "acknowledged",
    )
    await db.commit()
    return result
