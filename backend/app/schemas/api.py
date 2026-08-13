from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.events import TelemetryEvent


class HealthOut(BaseModel):
    status: str
    database: bool
    redis: bool
    app: str


class TelemetryIngestResponse(BaseModel):
    accepted: int
    event_ids: list[str]


class BinCounts(BaseModel):
    pass_count: int = Field(serialization_alias="pass", validation_alias="pass")
    retest: int
    fail: int
    reclass: int

    model_config = {"populate_by_name": True, "serialize_by_alias": True}


class HeaderStats(BaseModel):
    lots_in_test: int
    test_time_saved_hours: float
    overall_yield_pct: float


class DieTestResult(BaseModel):
    result: Literal["pass", "retest", "fail", "reclass", "untested"]
    fail_code: str | None = None
    test_time_ms: float | None = None
    confidence: float | None = None
    timestamp: datetime | None = None


class DieOut(BaseModel):
    die_id: str
    wafer_id: str
    x: int  # column
    y: int  # row
    row: int
    column: int
    result: Literal["pass", "retest", "fail", "reclass", "untested"]
    fail_code: str | None = None
    test_time_ms: float | None = None
    confidence: float | None = None
    timestamp: datetime | None = None
    # backward-compatible alias used by older clients
    bin: Literal["pass", "retest", "fail", "reclass", "untested"]


class WaferListItem(BaseModel):
    wafer_id: str
    lot_id: str
    status: str
    yield_pct: float
    total_dies: int
    tested_dies: int


class WaferDetail(WaferListItem):
    bin_counts: BinCounts
    caption: str
    pass_count: int = 0
    fail_count: int = 0
    retest_count: int = 0
    reclass_count: int = 0



class KpiHistoryPoint(BaseModel):
    timestamp: datetime
    value: float
    index: int | None = None


class KpiOut(BaseModel):
    id: str
    name: str
    value: float
    unit: str
    baseline: float
    target: float
    previous_value: float
    improvement: float
    trend: Literal["up", "down", "flat"]
    status: Literal["on_track", "at_risk", "below_target", "exceeds_target"]
    timestamp: datetime
    history: list[KpiHistoryPoint]
    description: str = ""
    accent: str = "#6EE7A8"


class KpisListOut(BaseModel):
    kpis: list[KpiOut]


class KpiHistoryOut(BaseModel):
    id: str
    name: str
    unit: str
    history: list[KpiHistoryPoint]


class KpiDetailOut(KpiOut):
    lots: int
    wafers: int
    testers: int
    sites: int
    recent_events: list["EventLogItem"]


# Legacy card shape still used inside dashboard summary
class KpiCard(BaseModel):
    key: str
    title: str
    value: float
    unit: str
    description: str
    accent: str
    trend: Literal["up", "down", "flat"]
    series: list[float]
    baseline: float = 0.0
    target: float = 0.0
    previous_value: float = 0.0
    improvement: float = 0.0
    status: str = "on_track"
    timestamp: datetime | None = None


class KpisOut(BaseModel):
    cards: list[KpiCard]


class MaintenanceAssetOut(BaseModel):
    asset_id: str
    name: str
    health_pct: float | None
    status: Literal["ok", "warn", "unavailable"]
    rul_days: float | None = None
    tester_id: str | None = None
    component: str | None = None
    failure_probability: float | None = None
    confidence: float | None = None
    severity: Literal["healthy", "watch", "warning", "critical", "offline", "unavailable"] = "unavailable"
    recommended_action: str | None = None
    model_available: bool = True
    message: str | None = None
    updated_at: datetime | None = None


class MaintenanceOut(BaseModel):
    flagged_count: int
    model_available: bool
    assets: list[MaintenanceAssetOut]


class MaintenanceHistoryItem(BaseModel):
    history_id: str
    tester_id: str
    component: str
    event_type: str
    detail: str
    health_score: float | None
    severity: str | None
    created_at: datetime


class MaintenanceHealthPoint(BaseModel):
    timestamp: datetime
    health_score: float | None
    failure_probability: float | None
    rul_days: float | None
    severity: str
    component: str


class MaintenanceTesterDetail(BaseModel):
    tester_id: str
    name: str
    status: str
    site_id: str | None
    overall_severity: Literal["healthy", "watch", "warning", "critical", "offline", "unavailable"]
    model_available: bool
    components: list[MaintenanceAssetOut]
    history: list[MaintenanceHistoryItem]
    health_series: list[MaintenanceHealthPoint]


class MaintenancePredictResponse(BaseModel):
    predictions: list[MaintenanceAssetOut]


class TestLimitOut(BaseModel):
    limit_id: str
    parameter: str
    test_name: str
    name: str  # display alias: parameter · test_name
    site_id: str | None = None
    tester_id: str | None = None
    lot_id: str | None = None
    previous_limit: float
    current_limit: float
    delta: float
    change_percentage: float
    change_pct: float  # alias of change_percentage for legacy clients
    change_label: str
    direction: Literal["tightened", "widened", "unchanged"]
    cpk: float | None = None
    target_cpk: float = 1.33
    confidence: float | None = None
    reason: str | None = None
    status: Literal["RECOMMENDED", "PENDING_APPROVAL", "ACTIVE", "REJECTED", "ROLLED_BACK"]
    created_at: datetime
    updated_at: datetime


class TestLimitsOut(BaseModel):
    adjustments_today: int
    items: list[TestLimitOut]


class TesterOut(BaseModel):
    tester_id: str
    name: str
    status: str
    site_id: str | None = None
    health_pct: float | None = None


class EventLogItem(BaseModel):
    event_id: str
    event_type: str
    timestamp: datetime
    tag: Literal["pass", "warn", "info"]
    text: str
    lot_id: str | None = None
    wafer_id: str | None = None
    tester_id: str | None = None


class DashboardSummary(BaseModel):
    header: HeaderStats
    active_wafer: WaferDetail | None
    kpis: list[KpiCard]
    maintenance: MaintenanceOut
    test_limits: TestLimitsOut
    recent_events: list[EventLogItem]
    connection_hint: str = "Live telemetry connected to local ATE optimization service"


class WsEnvelope(BaseModel):
    kind: Literal["telemetry_event", "projection_snapshot"]
    event: TelemetryEvent | None = None
    summary: DashboardSummary | None = None


KpiDetailOut.model_rebuild()
