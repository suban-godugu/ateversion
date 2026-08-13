from __future__ import annotations

from app.ml.predictive_maintenance.models import (
    HealthSeverity,
    MaintenanceRecommendation,
    TelemetryFeature,
)


def severity_from_prediction(
    *,
    health_score: float | None,
    failure_probability: float | None,
    rul_days: float | None,
    tester_online: bool,
    model_available: bool,
) -> HealthSeverity:
    if not model_available or health_score is None:
        return HealthSeverity.unavailable
    if not tester_online:
        return HealthSeverity.offline
    fp = failure_probability if failure_probability is not None else 0.0
    rul = rul_days if rul_days is not None else 99.0
    if health_score < 45 or fp >= 0.75 or rul <= 3:
        return HealthSeverity.critical
    if health_score < 65 or fp >= 0.55 or rul <= 7:
        return HealthSeverity.warning
    if health_score < 80 or fp >= 0.35 or rul <= 14:
        return HealthSeverity.watch
    return HealthSeverity.healthy


def build_recommendation(
    features: TelemetryFeature,
    *,
    health_score: float | None,
    failure_probability: float | None,
    rul_days: float | None,
    severity: HealthSeverity,
) -> MaintenanceRecommendation | None:
    if severity == HealthSeverity.unavailable:
        return None
    if severity == HealthSeverity.offline:
        return MaintenanceRecommendation(
            action="Restore tester connectivity and re-run prediction",
            priority="urgent",
            rationale="Tester is offline; health inference cannot be trusted until telemetry resumes.",
            suggested_window_days=0,
        )

    drivers: list[str] = []
    if features.contact_resistance >= 1.4:
        drivers.append("elevated contact resistance")
    if features.parametric_drift >= 4.0:
        drivers.append("parametric drift")
    if features.test_failures >= 15:
        drivers.append("rising test failures")
    if features.cycle_count >= 50000:
        drivers.append("high cycle count")
    if features.temperature >= 70:
        drivers.append("thermal stress")
    if not drivers:
        drivers.append("aggregate wear signature")

    rationale = (
        f"Model cites {', '.join(drivers)}. "
        f"health={health_score}, p_fail={failure_probability}, RUL={rul_days}d."
    )

    if severity == HealthSeverity.critical:
        return MaintenanceRecommendation(
            action=f"Schedule immediate service for {features.component}",
            priority="urgent",
            rationale=rationale,
            suggested_window_days=1.0,
        )
    if severity == HealthSeverity.warning:
        return MaintenanceRecommendation(
            action=f"Plan contactor/probe inspection on {features.component}",
            priority="high",
            rationale=rationale,
            suggested_window_days=min(float(rul_days or 7), 7.0),
        )
    if severity == HealthSeverity.watch:
        return MaintenanceRecommendation(
            action=f"Increase monitoring cadence for {features.component}",
            priority="medium",
            rationale=rationale,
            suggested_window_days=min(float(rul_days or 14), 14.0),
        )
    return MaintenanceRecommendation(
        action="Continue normal operation",
        priority="low",
        rationale=rationale,
        suggested_window_days=None,
    )
