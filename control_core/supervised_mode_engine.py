"""Restricted *supervised* SAJ H2 mode change engine (NOT connected to HA).

This is testable logic with a fake Modbus transport. Any live use requires
explicit per-operation hardware/profile authorization; that permission is
hardcoded OFF in this release, and the integration never imports this module.
Supported mode values: 0 (Self-use), 1 (Time-of-use). Never write 2 or 3.

A readback match confirms only a stored setting, not actual power direction.
No automatic rollback: writing a stale previous mode may undo a newer
eLEKeeper command. An operator must restore via the official app on error.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Protocol
import asyncio


MODE_REGISTER = 0x3647
FALLBACK_REGISTER = 0x365F
CHARGE_ENABLE_REGISTER = 0x3604
DISCHARGE_ENABLE_REGISTER = 0x3605


class ModeError(RuntimeError):
    pass


class Status(str, Enum):
    NO_CHANGE = "no_change"
    DISABLED = "hardware_writes_disabled"
    VERIFIED = "device_readback_verified"
    UNCONFIRMED = "unconfirmed"


@dataclass(frozen=True)
class Snapshot:
    mode: int
    fallback: int
    charge_mask: int
    discharge_mask: int


@dataclass(frozen=True)
class Result:
    status: Status
    before: Snapshot
    after: Snapshot
    wrote_register: bool
    message: str


class RegisterTransport(Protocol):
    async def read_holding(self, address: int, count: int) -> tuple[int, ...]: ...
    async def write_single(self, address: int, value: int) -> bool: ...


async def read_snapshot(transport: RegisterTransport) -> Snapshot:
    """Read twice and compare to catch app-originated concurrent changes."""
    async def once():
        # masks are consecutive in one read; mode/fallback each separately.
        masks = await transport.read_holding(CHARGE_ENABLE_REGISTER, 2)
        mode = await transport.read_holding(MODE_REGISTER, 1)
        fallback = await transport.read_holding(FALLBACK_REGISTER, 1)
        if len(masks) != 2 or len(mode) != 1 or len(fallback) != 1:
            raise ModeError("Incomplete inverter readback")
        values = (mode[0], fallback[0], masks[0], masks[1])
        if any(type(v) is not int for v in values):
            raise ModeError("Non-integer inverter readback")
        snapshot = Snapshot(*values)
        if snapshot.mode not in (0, 1):
            raise ModeError("Unsupported live mode: fail closed")
        if snapshot.fallback != 1:
            raise ModeError("Outside-TOU fallback not Self-consumption")
        if not 0 <= snapshot.charge_mask <= 127 or not 0 <= snapshot.discharge_mask <= 127:
            raise ModeError("Unknown schedule mask bits")
        return snapshot
    first, second = await once(), await once()
    if first != second:
        raise ModeError("Inverter settings changing during readback")
    return first


# Hard-disabled until a separate, owner-approved release explicitly changes
# this constant after model-specific safety review and mock test results.
LIVE_WRITE_ENABLED = False


async def supervised_mode_change(
    transport: RegisterTransport,
    target: int,
    *,
    confirm: str,
    profile_model: str,
    profile_control_firmware: str,
    interval_seconds: float = 10.0,
    max_checks: int = 30,
) -> Result:
    """A single mode-register write with pre/post validation if authorized.

    This function deliberately NEVER writes with the current release flag OFF.
    The guard is checked BEFORE opening a device write path.
    """
    if type(target) is not int or target not in (0, 1):
        raise ModeError("Only raw modes 0 and 1 are permitted")
    if profile_model != "H2-10K-S3-A" or profile_control_firmware != "v2.018":
        raise ModeError("Hardware profile not approved")
    if confirm != f"CHANGE_MODE_TO_{target}":
        raise ModeError("Explicit action-specific confirmation required")
    if not LIVE_WRITE_ENABLED:
        raise ModeError("Hardware mode writes disabled in this release")
    before = await read_snapshot(transport)
    if before.mode == target:
        return Result(Status.NO_CHANGE, before, before, False, "Already in target mode")
    # A second snapshot just before the write rejects app-originated changes.
    if await read_snapshot(transport) != before:
        raise ModeError("External mode or schedule edit: abort")
    # No retries; a lost ACK can still mean a real write succeeded.
    ack = await transport.write_single(MODE_REGISTER, target)
    if not ack:
        raise ModeError("Write acknowledgement missing: check app and readback manually")
    for _ in range(max_checks):
        await asyncio.sleep(interval_seconds)
        after = await read_snapshot(transport)
        if (after.fallback != before.fallback or
                after.charge_mask != before.charge_mask or
                after.discharge_mask != before.discharge_mask):
            raise ModeError("Schedules or fallback changed; manually inspect and restore")
        if after.mode == target:
            return Result(Status.VERIFIED, before, after, True,
                          "Inverter register saved; eLEKeeper may refresh later")
        if after.mode != before.mode:
            raise ModeError("Unexpected operating mode; manually inspect")
    raise ModeError("Timed out waiting for mode readback; no automatic retry or rollback")
