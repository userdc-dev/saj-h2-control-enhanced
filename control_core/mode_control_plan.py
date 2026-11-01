"""Fail-closed, no-write planning for future SAJ H2 controls.

This module DOES NOT send any Modbus command. It produces a reviewed
proposal bound to an *observed* inverter config and requires exact-match
readback checks. Separate explicit live-write approval and tested hardware
adapter will be required before any proposal could be acted upon.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

class RequestedMode(str, Enum):
    SELF_CONSUMPTION = "self_consumption"
    TIME_OF_USE = "time_of_use"

MODE_CODES = {
    RequestedMode.SELF_CONSUMPTION: 0,
    RequestedMode.TIME_OF_USE: 1,
}

class UnsafeControlRequest(ValueError):
    pass

@dataclass(frozen=True)
class Readback:
    mode_raw: int
    fallback_raw: int
    charge_mask: int
    discharge_mask: int
    observed_at: datetime

    def __post_init__(self):
        if self.observed_at.tzinfo is None:
            raise UnsafeControlRequest("Device readback must have timezone-aware timestamp")
        if self.mode_raw not in (0, 1):
            raise UnsafeControlRequest("Inverter in unsupported mode; refuse all changes")
        if self.fallback_raw != 1:
            raise UnsafeControlRequest("TOU fallback must be Self-consumption")
        if not 0 <= self.charge_mask <= 127 or not 0 <= self.discharge_mask <= 127:
            raise UnsafeControlRequest("Unrecognised schedule bits")

@dataclass(frozen=True)
class ModeProposal:
    previous_mode_raw: int
    desired_mode_raw: int
    preserved_fallback_raw: int
    preserved_charge_mask: int
    preserved_discharge_mask: int
    source_read_at: datetime
    proposed_at: datetime
    request_is_noop: bool
    permitted_to_write: bool = False

    @property
    def explanation(self):
        return (
            "No change needed; device already matches requested mode"
            if self.request_is_noop else
            "DRY RUN ONLY: mode change not approved or implemented"
        )


def plan_mode_change(
    current: Readback,
    requested: RequestedMode,
    *,
    now: datetime,
    max_age_seconds: int = 180,
) -> ModeProposal:
    if not isinstance(requested, RequestedMode):
        raise UnsafeControlRequest("Only Self-consumption or Time-of-use can be requested")
    if now.tzinfo is None:
        raise UnsafeControlRequest("Now must include timezone")
    age = (now - current.observed_at).total_seconds()
    if not 0 <= age <= max_age_seconds:
        raise UnsafeControlRequest("Missing, future, or stale inverter snapshot")
    target = MODE_CODES[requested]
    return ModeProposal(
        previous_mode_raw=current.mode_raw,
        desired_mode_raw=target,
        preserved_fallback_raw=current.fallback_raw,
        preserved_charge_mask=current.charge_mask,
        preserved_discharge_mask=current.discharge_mask,
        source_read_at=current.observed_at,
        proposed_at=now,
        request_is_noop=target == current.mode_raw,
    )


def check_before_execution(proposal: ModeProposal, current: Readback, *, now: datetime):
    """Validate changes since proposal; always refuse execution for now."""
    if current.observed_at < proposal.source_read_at:
        raise UnsafeControlRequest("Observation predates planning snapshot")
    if (current.mode_raw != proposal.previous_mode_raw or
            current.fallback_raw != proposal.preserved_fallback_raw or
            current.charge_mask != proposal.preserved_charge_mask or
            current.discharge_mask != proposal.preserved_discharge_mask):
        raise UnsafeControlRequest("Another controller changed the inverter configuration")
    if (now - current.observed_at).total_seconds() not in range(0, 181):
        raise UnsafeControlRequest("Device state is stale")
    raise UnsafeControlRequest("Live inverter writes are disabled: no authorized hardware adapter")
