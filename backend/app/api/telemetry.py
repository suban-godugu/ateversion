from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AuthUser, require_permissions
from app.core.database import get_db
from app.core.rbac import Permission
from app.schemas.api import TelemetryIngestResponse
from app.schemas.events import TelemetryEvent, TelemetryEventBatch
from app.services.telemetry_service import ingest_events

router = APIRouter()


@router.post("/telemetry/events", response_model=TelemetryIngestResponse)
async def post_telemetry_events(
    body: TelemetryEvent | TelemetryEventBatch,
    db: AsyncSession = Depends(get_db),
    _: AuthUser = Depends(require_permissions(Permission.WRITE_TELEMETRY)),
) -> TelemetryIngestResponse:
    events = body.events if isinstance(body, TelemetryEventBatch) else [body]
    # Sequence validation — reject negative / non-monotonic batches within request
    seen_ids: set[str] = set()
    last_seq: int | None = None
    for ev in events:
        if ev.event_id in seen_ids:
            raise HTTPException(status_code=422, detail=f"Duplicate event_id in batch: {ev.event_id}")
        seen_ids.add(ev.event_id)
        if ev.sequence_number < 0:
            raise HTTPException(status_code=422, detail="sequence_number must be >= 0")
        if last_seq is not None and ev.sequence_number < last_seq:
            raise HTTPException(
                status_code=422,
                detail="sequence_number must be non-decreasing within a batch",
            )
        last_seq = ev.sequence_number

    accepted = await ingest_events(db, events)
    return TelemetryIngestResponse(accepted=len(accepted), event_ids=accepted)
