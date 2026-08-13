from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class EventSeverity(str, Enum):
    INFO = "INFO"
    PASS = "PASS"
    WARN = "WARN"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class TestEvent(BaseModel):
    event_id: str
    timestamp: datetime
    severity: EventSeverity
    event_type: str
    source: str
    tester_id: str | None = None
    site_id: str | None = None
    lot_id: str | None = None
    wafer_id: str | None = None
    die_id: str | None = None
    message: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    acknowledged: bool = False
    acknowledged_by: str | None = None
    acknowledged_at: datetime | None = None
    sequence_number: int = 0


class TestEventsListOut(BaseModel):
    total: int
    unacknowledged: int
    items: list[TestEvent]


class AcknowledgeRequest(BaseModel):
    actor: str = "engineer"
    comment: str | None = None


class EventFilterParams(BaseModel):
    q: str | None = None
    tester_id: str | None = None
    site_id: str | None = None
    lot_id: str | None = None
    wafer_id: str | None = None
    severity: list[EventSeverity] | None = None
    event_type: str | None = None
    acknowledged: bool | None = None
    since: datetime | None = None
    until: datetime | None = None
    limit: int = 100
    offset: int = 0
