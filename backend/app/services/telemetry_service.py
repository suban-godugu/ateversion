from __future__ import annotations

import json
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.redis import publish_event
from app.models.entities import TelemetryEventRow
from app.schemas.events import EventType, TelemetryEvent
from app.services.event_text import tag_for_event, text_for_event
from app.services.projections import apply_event_projections
from app.services.test_events.severity import severity_for_event

VALID_SOURCES = {"stdf", "ate", "test_log", "ingestion", "ml", "seed", "worker"}


def validate_event(event: TelemetryEvent) -> TelemetryEvent:
    if event.event_type not in EventType:
        raise HTTPException(status_code=422, detail=f"Unknown event_type: {event.event_type}")
    if not event.source:
        raise HTTPException(status_code=422, detail="source is required")
    if event.sequence_number is None or event.sequence_number < 0:
        raise HTTPException(status_code=422, detail="sequence_number must be >= 0")
    if event.timestamp.tzinfo is not None:
        event.timestamp = event.timestamp.replace(tzinfo=None)
    return event


def normalize_event(event: TelemetryEvent) -> TelemetryEvent:
    """Normalize identifiers and die coordinates into canonical form."""
    payload = dict(event.payload or {})
    if event.die_id and "x" not in payload:
        raw = event.die_id.replace("(", "").replace(")", "")
        if "," in raw:
            parts = raw.split(",")
            if len(parts) == 2 and parts[0].strip().lstrip("-").isdigit():
                payload["x"] = int(parts[0].strip())
                payload["y"] = int(parts[1].strip())
                event.die_id = f"{payload['x']},{payload['y']}"
    if event.event_type.value.startswith("die_") and event.wafer_id and "x" in payload and "y" in payload:
        # Canonical die primary key uses wafer prefix in projections
        pass
    if event.lot_id:
        event.lot_id = event.lot_id.strip()
    if event.wafer_id:
        event.wafer_id = event.wafer_id.strip()
    event.payload = payload
    return event


async def ingest_events(
    db: AsyncSession,
    events: list[TelemetryEvent],
    *,
    publish: bool = True,
    materialize_floor_log: bool = True,
) -> list[str]:
    settings = get_settings()
    accepted: list[str] = []
    wafers_touched: set[str] = set()

    for raw in events:
        event = normalize_event(validate_event(raw))
        existing = await db.get(TelemetryEventRow, event.event_id)
        if existing is not None:
            continue

        row = TelemetryEventRow(
            event_id=event.event_id,
            event_type=event.event_type.value,
            timestamp=event.timestamp or datetime.utcnow(),
            source=event.source,
            tester_id=event.tester_id,
            site_id=event.site_id,
            lot_id=event.lot_id,
            wafer_id=event.wafer_id,
            die_id=event.die_id,
            sequence_number=event.sequence_number,
            payload=event.payload,
            log_tag=tag_for_event(event.event_type, event),
            log_text=text_for_event(event),
        )
        db.add(row)
        await apply_event_projections(
            db,
            event,
            defer_yield=event.event_type.value.startswith("die_"),
            materialize_floor_log=materialize_floor_log,
        )
        if event.wafer_id and event.event_type.value.startswith("die_"):
            wafers_touched.add(event.wafer_id)
        accepted.append(event.event_id)
        await db.flush()

        if publish:
            severity = severity_for_event(event)
            message = text_for_event(event)
            test_event = {
                "event_id": event.event_id,
                "timestamp": event.timestamp.isoformat() if event.timestamp else None,
                "severity": severity.value,
                "event_type": event.event_type.value,
                "source": event.source,
                "tester_id": event.tester_id,
                "site_id": event.site_id,
                "lot_id": event.lot_id,
                "wafer_id": event.wafer_id,
                "die_id": event.die_id,
                "message": message,
                "metadata": event.payload or {},
                "acknowledged": False,
                "sequence_number": event.sequence_number,
            }
            await publish_event(
                settings.telemetry_channel,
                json.dumps(
                    {
                        "kind": "telemetry_event",
                        "event": json.loads(event.model_dump_json()),
                        "test_event": test_event,
                    }
                ),
            )

    if wafers_touched:
        from app.services.projections import recompute_wafer_yield, ensure_dashboard_state

        state = await ensure_dashboard_state(db)
        for wid in wafers_touched:
            wafer = await recompute_wafer_yield(db, wid)
            if wafer:
                state.active_wafer_id = wid
                state.overall_yield_pct = wafer.yield_pct

    await db.commit()
    return accepted
