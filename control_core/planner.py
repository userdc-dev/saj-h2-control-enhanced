"""Validates potential charge/discharge requests; does not execute them."""
from dataclasses import dataclass
from enum import Enum
from .telemetry import TelemetryResult

BLOCKED_MODES = frozenset((2, 3))

class Direction(str, Enum):
    CHARGE = "charge"
    DISCHARGE = "discharge"

@dataclass(frozen=True)
class ProposedAction:
    direction: Direction
    minutes: int
    requested_power_w: int | None  # None represents 'max', unresolved until discovery

@dataclass(frozen=True)
class PlanReview:
    allowed_to_execute: bool
    reasons: tuple[str, ...]
    proposal: ProposedAction | None

def review_action(
    direction: str,
    minutes: int,
    requested_power_w: int | None,
    telemetry: TelemetryResult,
) -> PlanReview:
    issues = []
    try:
        parsed_direction = Direction(direction)
    except (ValueError, TypeError):
        parsed_direction = None
        issues.append("Unsupported action direction")
    if type(minutes) is not int or not 1 <= minutes <= 120:
        issues.append("Duration must be an integer 1..120 minutes (initial UI design bound)")
    if requested_power_w is not None and (type(requested_power_w) is not int or requested_power_w <= 0):
        issues.append("Power must be positive integer watts or None for unresolved maximum")
    if telemetry.snapshot is None:
        issues.append("Telemetry invalid or not verified")
    else:
        if telemetry.snapshot.mode not in ("Self-consumption", "Time-of-use"):
            issues.append("Inverter mode not eligible for consideration")
    if requested_power_w is None:
        issues.append("'Max power' capability not independently verified")
    else:
        issues.append("Power capability and hardware write register not verified")
    issues.append("Hardware control, verified stop and watchdog are not implemented")
    proposal = (
        ProposedAction(parsed_direction, minutes, requested_power_w)
        if parsed_direction is not None and type(minutes) is int and 1 <= minutes <= 120
        else None
    )
    return PlanReview(allowed_to_execute=False, reasons=tuple(issues), proposal=proposal)
