from __future__ import annotations

from app.schemas.events import EventType, TelemetryEvent
from app.services.test_events.models import EventSeverity


_PASS = {
    EventType.die_pass,
    EventType.die_reclassified,
    EventType.lot_completed,
    EventType.optimization_completed,
}
_WARN = {
    EventType.die_retest,
    EventType.dynamic_limit_updated,
    EventType.tester_status_changed,
    EventType.wafer_progress,
}
_ERROR = {
    EventType.die_fail,
    EventType.escape_risk_detected,
    EventType.engineering_hold,
}
_CRITICAL_HINTS = {"critical", "offline", "emergency"}


def severity_for_event(event: TelemetryEvent) -> EventSeverity:
    """Authoritative severity classification — never computed in React."""
    et = event.event_type
    payload = event.payload or {}

    if et == EventType.predictive_maintenance:
        sev = str(payload.get("severity", "")).lower()
        if sev == "critical" or payload.get("status") == "critical":
            return EventSeverity.CRITICAL
        if sev in {"warning", "warn", "watch"}:
            return EventSeverity.WARN
        if sev == "unavailable":
            return EventSeverity.ERROR
        return EventSeverity.WARN

    if et == EventType.tester_status_changed:
        status = str(payload.get("status", "")).lower()
        if status in _CRITICAL_HINTS:
            return EventSeverity.CRITICAL
        if status in {"degraded", "warn", "warning"}:
            return EventSeverity.WARN
        return EventSeverity.INFO

    if et == EventType.engineering_hold:
        if str(payload.get("priority", "")).lower() in _CRITICAL_HINTS:
            return EventSeverity.CRITICAL
        return EventSeverity.ERROR

    if et in _PASS:
        return EventSeverity.PASS
    if et in _ERROR:
        return EventSeverity.ERROR
    if et in _WARN:
        return EventSeverity.WARN
    return EventSeverity.INFO


def tag_from_severity(severity: EventSeverity) -> str:
    if severity == EventSeverity.PASS:
        return "pass"
    if severity in {EventSeverity.WARN, EventSeverity.ERROR, EventSeverity.CRITICAL}:
        return "warn"
    return "info"
