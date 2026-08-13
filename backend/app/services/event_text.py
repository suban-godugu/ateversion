from __future__ import annotations

from app.schemas.events import EventType, TelemetryEvent
from app.services.test_events.severity import severity_for_event, tag_from_severity


def tag_for_event(event_type: EventType, event: TelemetryEvent | None = None) -> str:
    if event is not None:
        return tag_from_severity(severity_for_event(event))
    # Fallback when only type is known
    from app.services.test_events.models import EventSeverity

    probe = TelemetryEvent(
        event_type=event_type,
        source="probe",
        sequence_number=0,
        payload={},
    )
    return tag_from_severity(severity_for_event(probe))



def text_for_event(event: TelemetryEvent) -> str:
    p = event.payload or {}
    et = event.event_type

    if et == EventType.die_reclassified:
        return (
            f"Die ({event.die_id}) reclassified pass — false-fail model overturned "
            f"Pattern Grp {p.get('pattern_group', '—')} flag."
        )
    if et == EventType.predictive_maintenance:
        return (
            f"{p.get('asset_name', event.tester_id or 'Tester')} — predictive maintenance flag "
            f"raised, RUL {p.get('rul_days', '—')} days."
        )
    if et == EventType.dynamic_limit_updated:
        pct = p.get("change_percentage", p.get("change_pct", 0))
        return (
            f"{p.get('parameter', 'Limit')} on {p.get('test_name', event.site_id or 'site')} "
            f"{p.get('direction', 'adjusted')} {abs(float(pct or 0)):.1f}% "
            f"({p.get('status', 'ACTIVE')}) following Cpk trend review."
        )
    if et == EventType.lot_completed:
        return (
            f"Lot {event.lot_id} completed — {p.get('test_time_reduction_pct', '—')}% "
            "test time reduction vs. static pattern order."
        )
    if et == EventType.pattern_optimization:
        return (
            f"Vector/pattern optimization applied — "
            f"{p.get('summary', 'coverage-preserving reduction')}."
        )
    if et == EventType.escape_risk_detected:
        return (
            f"Escape-risk outlier detected on Die ({event.die_id}) — routed to engineering hold."
        )
    if et == EventType.die_retest:
        return f"Retest trigger on Die ({event.die_id}) — confidence score warrants re-test."
    if et == EventType.yield_updated:
        return f"Yield updated to {p.get('yield_pct', '—')}% for wafer {event.wafer_id}."
    if et == EventType.test_time_updated:
        return f"Test time saved (24h) now {p.get('hours_saved_24h', '—')} hrs."
    if et == EventType.wafer_started:
        return f"Wafer {event.wafer_id} started on tester {event.tester_id}."
    if et == EventType.wafer_progress:
        return f"Wafer {event.wafer_id} progress {p.get('tested_dies', '—')}/{p.get('total_dies', '—')} dies."
    if et == EventType.lot_started:
        return f"Lot {event.lot_id} started."
    if et == EventType.die_pass:
        return f"Die ({event.die_id}) passed."
    if et == EventType.die_fail:
        return f"Die ({event.die_id}) failed."
    if et == EventType.die_tested:
        return f"Die ({event.die_id}) tested — bin {p.get('bin', '—')}."
    if et == EventType.tester_status_changed:
        return f"Tester {event.tester_id} status → {p.get('status', '—')}."
    if et == EventType.engineering_hold:
        return f"Engineering hold — {p.get('reason', 'manual hold')}."
    if et == EventType.optimization_completed:
        return f"Optimization completed — {p.get('summary', 'strategy applied')}."
    return f"{et.value} received from {event.source}."
