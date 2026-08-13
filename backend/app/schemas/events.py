from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class EventType(str, Enum):
    wafer_started = "wafer_started"
    wafer_progress = "wafer_progress"
    die_tested = "die_tested"
    die_pass = "die_pass"
    die_fail = "die_fail"
    die_retest = "die_retest"
    die_reclassified = "die_reclassified"
    lot_started = "lot_started"
    lot_completed = "lot_completed"
    yield_updated = "yield_updated"
    test_time_updated = "test_time_updated"
    pattern_optimization = "pattern_optimization"
    predictive_maintenance = "predictive_maintenance"
    dynamic_limit_updated = "dynamic_limit_updated"
    escape_risk_detected = "escape_risk_detected"
    tester_status_changed = "tester_status_changed"
    engineering_hold = "engineering_hold"
    optimization_completed = "optimization_completed"


class TelemetryEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    event_type: EventType
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    source: str
    tester_id: str | None = None
    site_id: str | None = None
    lot_id: str | None = None
    wafer_id: str | None = None
    die_id: str | None = None
    sequence_number: int
    payload: dict[str, Any] = Field(default_factory=dict)


class TelemetryEventBatch(BaseModel):
    events: list[TelemetryEvent]
