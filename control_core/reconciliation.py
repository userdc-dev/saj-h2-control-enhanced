"""Pure data model for future SAJ TOU configuration reconciliation.

NO Home Assistant or Modbus dependency. NO writes. This is deliberately
conservative: an app or HA request is not confirmed until the actual device
configuration matches the expected canonical *raw* values.

The owner's eLEKeeper settings can take approximately 5 minutes to activate.
A 10-minute verification window below is an initial design choice, NOT a
guarantee that SAJ will comply or a reason to repeat commands.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Hashable


class State(str, Enum):
    NOT_REQUESTED = "not_requested"
    WAITING_FOR_DEVICE = "waiting_for_device"
    SAVED_ON_DEVICE = "saved_on_device"
    UNCONFIRMED_TIMEOUT = "unconfirmed_timeout"
    OBSERVATION_STALE = "observation_stale"


@dataclass(frozen=True)
class RequestedConfiguration:
    expected_raw: Hashable
    submitted_at: datetime
    verification_timeout_s: int = 600

    def __post_init__(self):
        if self.submitted_at.tzinfo is None:
            raise ValueError("submit timestamp must be timezone aware")
        if type(self.verification_timeout_s) is not int or not 60 <= self.verification_timeout_s <= 3600:
            raise ValueError("invalid bounded verification timeout")


@dataclass(frozen=True)
class DeviceObservation:
    actual_raw: Hashable
    observed_at: datetime
    reliable: bool = True

    def __post_init__(self):
        if self.observed_at.tzinfo is None:
            raise ValueError("observation timestamp must be timezone aware")


@dataclass(frozen=True)
class Reconciliation:
    state: State
    applied: bool
    detail: str


def reconcile(
    requested: RequestedConfiguration | None,
    observation: DeviceObservation | None,
    *,
    now: datetime,
    max_observation_age_s: int = 180,
) -> Reconciliation:
    """Only compare raw canonical settings; never approve physical writes.

    Does NOT infer a schedule's physical effect (charging/discharging)
    simply because the device has stored its configuration.
    """
    if now.tzinfo is None:
        raise ValueError("now must be timezone aware")
    if requested is None:
        return Reconciliation(State.NOT_REQUESTED, False,
                              "Device readback only; no pending local request")
    if observation is None or not observation.reliable:
        return Reconciliation(State.OBSERVATION_STALE, False,
                              "No trustworthy device readback")
    age = (now - observation.observed_at).total_seconds()
    if age < 0 or age > max_observation_age_s:
        return Reconciliation(State.OBSERVATION_STALE, False,
                              "Device readback is missing, future-dated or stale")
    if observation.observed_at < requested.submitted_at:
        return Reconciliation(State.WAITING_FOR_DEVICE, False,
                              "Reading predates the request")
    if observation.actual_raw == requested.expected_raw:
        return Reconciliation(State.SAVED_ON_DEVICE, True,
                              "Saved configuration read back; execution unverified")
    since = (now - requested.submitted_at).total_seconds()
    if since <= requested.verification_timeout_s:
        return Reconciliation(State.WAITING_FOR_DEVICE, False,
                              "Device still reports earlier or different settings")
    return Reconciliation(State.UNCONFIRMED_TIMEOUT, False,
                          "Device settings do not match; do not retry automatically")
