from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class HealthSeverity(str, Enum):
    healthy = "healthy"
    watch = "watch"
    warning = "warning"
    critical = "critical"
    offline = "offline"
    unavailable = "unavailable"


class TelemetryFeature(BaseModel):
    """Input feature vector for the predictive maintenance model."""

    tester_id: str
    component: str
    test_failures: float = 0.0
    parametric_drift: float = 0.0
    contact_resistance: float = 0.0
    temperature: float = 0.0
    voltage_deviation: float = 0.0
    current_deviation: float = 0.0
    cycle_count: float = 0.0
    historical_failures: float = 0.0
    maintenance_events: float = 0.0
    tester_utilization: float = 0.0
    captured_at: datetime = Field(default_factory=datetime.utcnow)

    def as_vector(self) -> list[float]:
        return [
            self.test_failures,
            self.parametric_drift,
            self.contact_resistance,
            self.temperature,
            self.voltage_deviation,
            self.current_deviation,
            self.cycle_count,
            self.historical_failures,
            self.maintenance_events,
            self.tester_utilization,
        ]


class MaintenanceRecommendation(BaseModel):
    action: str
    priority: Literal["low", "medium", "high", "urgent"]
    rationale: str
    suggested_window_days: float | None = None


class MaintenancePrediction(BaseModel):
    tester_id: str
    component: str
    health_score: float | None
    failure_probability: float | None
    rul_days: float | None
    severity: HealthSeverity
    confidence: float | None
    recommended_action: str | None
    recommendation: MaintenanceRecommendation | None = None
    timestamp: datetime
    model_available: bool = True
    message: str | None = None


class TesterHealth(BaseModel):
    tester_id: str
    name: str
    status: str
    site_id: str | None
    components: list[MaintenancePrediction]
    overall_severity: HealthSeverity
    model_available: bool
    latest_timestamp: datetime | None = None


class PredictRequest(BaseModel):
    tester_id: str | None = None
    component: str | None = None
    features: TelemetryFeature | None = None
    publish: bool = True


FEATURE_NAMES = [
    "test_failures",
    "parametric_drift",
    "contact_resistance",
    "temperature",
    "voltage_deviation",
    "current_deviation",
    "cycle_count",
    "historical_failures",
    "maintenance_events",
    "tester_utilization",
]
