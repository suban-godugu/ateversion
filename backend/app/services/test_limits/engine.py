from __future__ import annotations

import math
from dataclasses import dataclass

from app.services.test_limits.models import LimitDirection


@dataclass(frozen=True)
class LimitProposal:
    previous_limit: float
    current_limit: float
    delta: float
    change_percentage: float
    direction: LimitDirection
    cpk: float
    target_cpk: float
    confidence: float
    reason: str
    requires_approval: bool


def calculate_cpk(
    values: list[float],
    *,
    lsl: float | None,
    usl: float | None,
) -> float:
    """Process capability index. Pure Python — authoritative."""
    if not values:
        raise ValueError("samples required to calculate Cpk")
    if lsl is None and usl is None:
        raise ValueError("at least one of lsl/usl is required")

    n = len(values)
    mean = sum(values) / n
    if n < 2:
        std = 0.0
    else:
        var = sum((v - mean) ** 2 for v in values) / (n - 1)
        std = math.sqrt(var)

    if std <= 1e-12:
        # Degenerate distribution — capability is numerically huge if inside limits
        if (lsl is None or mean >= lsl) and (usl is None or mean <= usl):
            return 99.0
        return 0.0

    candidates: list[float] = []
    if usl is not None:
        candidates.append((usl - mean) / (3.0 * std))
    if lsl is not None:
        candidates.append((mean - lsl) / (3.0 * std))
    return round(min(candidates), 4)


def calculate_limit_adjustment(
    *,
    previous_limit: float,
    values: list[float],
    lsl: float | None,
    usl: float | None,
    target_cpk: float = 1.33,
    is_upper_limit: bool = True,
) -> LimitProposal:
    """
    Recommend a new guard-band limit from rolling process capability.
    Tightens when Cpk is high; widens cautiously when Cpk is below target.
    """
    cpk = calculate_cpk(values, lsl=lsl, usl=usl)
    mean = sum(values) / len(values)
    std = 0.0
    if len(values) >= 2:
        var = sum((v - mean) ** 2 for v in values) / (len(values) - 1)
        std = math.sqrt(var)

    # Propose limit at target_cpk * 3σ from mean on the relevant side
    if is_upper_limit:
        proposed = mean + target_cpk * 3.0 * max(std, abs(previous_limit) * 0.001)
        # Never propose a looser absolute magnitude jump beyond policy in one step
    else:
        proposed = mean - target_cpk * 3.0 * max(std, abs(previous_limit) * 0.001)

    # Blend toward previous to avoid shock changes (max 8% absolute move)
    max_step = abs(previous_limit) * 0.08 if previous_limit != 0 else 0.08
    raw_delta = proposed - previous_limit
    if abs(raw_delta) > max_step:
        proposed = previous_limit + math.copysign(max_step, raw_delta)

    proposed = round(proposed, 6)
    delta = round(proposed - previous_limit, 6)
    if previous_limit == 0:
        change_pct = 0.0 if delta == 0 else 100.0
    else:
        change_pct = round((delta / abs(previous_limit)) * 100.0, 4)

    if abs(delta) < 1e-9:
        direction = LimitDirection.unchanged
    elif is_upper_limit:
        # Lower upper-limit => tightened; higher => widened
        direction = LimitDirection.tightened if delta < 0 else LimitDirection.widened
    else:
        # Higher lower-limit => tightened
        direction = LimitDirection.tightened if delta > 0 else LimitDirection.widened

    # Confidence from sample size and Cpk headroom
    n = len(values)
    sample_factor = min(1.0, n / 50.0)
    cpk_factor = min(1.0, max(0.0, cpk / max(target_cpk, 1e-6)))
    confidence = round(0.45 + 0.35 * sample_factor + 0.2 * cpk_factor, 3)

    if cpk >= target_cpk:
        reason = (
            f"Cpk {cpk:.2f} exceeds target {target_cpk:.2f}; "
            f"recommend {direction.value} limit by {abs(change_pct):.1f}%."
        )
    else:
        reason = (
            f"Cpk {cpk:.2f} below target {target_cpk:.2f}; "
            f"recommend {direction.value} limit by {abs(change_pct):.1f}% to restore capability."
        )

    requires_approval = require_approval(
        change_percentage=change_pct,
        cpk=cpk,
        target_cpk=target_cpk,
        confidence=confidence,
        direction=direction,
    )

    return LimitProposal(
        previous_limit=previous_limit,
        current_limit=proposed,
        delta=delta,
        change_percentage=change_pct,
        direction=direction,
        cpk=cpk,
        target_cpk=target_cpk,
        confidence=confidence,
        reason=reason,
        requires_approval=requires_approval,
    )


def validate_limit_change(
    *,
    previous_limit: float,
    proposed_limit: float,
    max_abs_pct: float = 10.0,
) -> tuple[bool, str]:
    if math.isnan(proposed_limit) or math.isinf(proposed_limit):
        return False, "proposed limit is not finite"
    if previous_limit == 0:
        return True, "ok"
    pct = abs((proposed_limit - previous_limit) / abs(previous_limit)) * 100.0
    if pct > max_abs_pct:
        return False, f"change {pct:.2f}% exceeds policy max {max_abs_pct:.1f}%"
    return True, "ok"


def require_approval(
    *,
    change_percentage: float,
    cpk: float,
    target_cpk: float,
    confidence: float,
    direction: LimitDirection,
) -> bool:
    """Large moves, low confidence, or widening always require human approval."""
    if direction == LimitDirection.widened:
        return True
    if abs(change_percentage) >= 3.0:
        return True
    if confidence < 0.7:
        return True
    if cpk < target_cpk:
        return True
    return False


def generate_limit_recommendation(
    *,
    previous_limit: float,
    values: list[float],
    lsl: float | None,
    usl: float | None,
    target_cpk: float = 1.33,
    is_upper_limit: bool = True,
) -> LimitProposal:
    proposal = calculate_limit_adjustment(
        previous_limit=previous_limit,
        values=values,
        lsl=lsl,
        usl=usl,
        target_cpk=target_cpk,
        is_upper_limit=is_upper_limit,
    )
    ok, msg = validate_limit_change(
        previous_limit=previous_limit,
        proposed_limit=proposal.current_limit,
    )
    if ok:
        return proposal

    # Clamp to policy max (±10%) and rebuild proposal fields
    max_step = abs(previous_limit) * 0.10 if previous_limit != 0 else 0.10
    clamped = round(previous_limit + math.copysign(max_step, proposal.delta or 1.0), 6)
    delta = round(clamped - previous_limit, 6)
    change_pct = (
        0.0
        if previous_limit == 0
        else round((delta / abs(previous_limit)) * 100.0, 4)
    )
    if abs(delta) < 1e-9:
        direction = LimitDirection.unchanged
    elif is_upper_limit:
        direction = LimitDirection.tightened if delta < 0 else LimitDirection.widened
    else:
        direction = LimitDirection.tightened if delta > 0 else LimitDirection.widened

    confidence = proposal.confidence
    requires = require_approval(
        change_percentage=change_pct,
        cpk=proposal.cpk,
        target_cpk=target_cpk,
        confidence=confidence,
        direction=direction,
    )
    return LimitProposal(
        previous_limit=previous_limit,
        current_limit=clamped,
        delta=delta,
        change_percentage=change_pct,
        direction=direction,
        cpk=proposal.cpk,
        target_cpk=target_cpk,
        confidence=confidence,
        reason=f"{proposal.reason} Clamped to policy ({msg}).",
        requires_approval=requires,
    )


def change_label(direction: LimitDirection, change_percentage: float) -> str:
    if direction == LimitDirection.unchanged:
        return "0.0% unchanged"
    sign = "−" if direction == LimitDirection.tightened else "+"
    return f"{sign}{abs(change_percentage):.1f}% {direction.value}"
