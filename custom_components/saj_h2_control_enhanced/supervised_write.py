"""Explicitly supervised, one-shot SAJ H2 mode experiment.

Supports 0 -> 1 and 1 -> 0 only, with separate exact confirmations. The user
must manually invoke the HA action with an exact confirmation phrase.
This module is NOT imported by any polling path or dashboard.

Only write: Modbus function 06 to 0x3647, value 0 or 1. Never write schedules/fallback.
No automatic retry or rollback because a VPP/elekeeper may act concurrently.
"""
import asyncio
import inspect
import logging

from pymodbus.client import AsyncModbusTcpClient

from .const import UNIT_ID
from .tou_protocol import (
    CHARGE_START, CHARGE_COUNT, DISCHARGE_START, DISCHARGE_COUNT,
    MODE_ADDR, FALLBACK_ADDR, decode_config, active_signature,
)

_LOGGER = logging.getLogger(__name__)
CONFIRM_PHRASES = {
    1: "I AUTHORIZE ONE TOU MODE WRITE",
    0: "I AUTHORIZE ONE SELF CONSUMPTION MODE WRITE",
}
_HARDWARE_MODEL = "H2-10K-S3-A"
_CONTROL_FIRMWARE = "v2.018"


class SupervisedWriteError(RuntimeError):
    """A supervised test was blocked or could not be confirmed."""


async def _snapshot(client):
    reader = client.read_holding_registers
    key = "device_id" if "device_id" in inspect.signature(reader).parameters else "slave"

    async def get(address, count):
        response = await reader(address=address, count=count, **{key: UNIT_ID})
        if response is None or response.isError() or len(response.registers) != count:
            raise SupervisedWriteError(f"Invalid Modbus readback at {address:#06x}")
        return tuple(response.registers)

    async def once():
        ch = await get(CHARGE_START, CHARGE_COUNT)
        dis = await get(DISCHARGE_START, DISCHARGE_COUNT)
        mode = (await get(MODE_ADDR, 1))[0]
        fallback = (await get(FALLBACK_ADDR, 1))[0]
        result = decode_config(ch, dis, mode, fallback)
        if result.mode not in (0, 1) or result.fallback != 1:
            raise SupervisedWriteError("Unsupported mode/fallback: no write")
        if not 0 <= result.charge_mask <= 127 or not 0 <= result.discharge_mask <= 127:
            raise SupervisedWriteError("Unsupported active slot masks")
        # Mode switching works after any valid schedule edit, not just the
        # owner's initial Friday/Wednesday baseline.
        for group in (result.charge_slots, result.discharge_slots):
            for slot in group:
                if not slot.enabled:
                    continue
                if not (1 <= slot.day_mask <= 127 and
                        1 <= slot.power_percent <= 100 and
                        slot.start != "unknown" and slot.end != "unknown"):
                    raise SupervisedWriteError(
                        "Invalid active slot; refuse mode change")
        return result

    first = await once()
    second = await once()
    if first != second:
        raise SupervisedWriteError("Inverter settings changed during verification")
    return second


async def run_supervised_tou_test(
    *, host, port, confirmed_phrase, expected_mode,
    device_model, control_firmware, target_mode=1,
    sleep=asyncio.sleep, client_factory=AsyncModbusTcpClient,
):
    """One write at most, preceded by two complete schedule snapshots.

    Returns a response compatible with HA service action response.
    Only an actual HA user action with the exact phrase can invoke this.
    """
    if type(target_mode) is not int or target_mode not in (0, 1):
        raise SupervisedWriteError("Only Self-consumption and Time-of-Use allowed")
    if confirmed_phrase != CONFIRM_PHRASES[target_mode]:
        raise SupervisedWriteError("Exact target-specific confirmation phrase required")
    if type(expected_mode) is not int or expected_mode != 1 - target_mode:
        raise SupervisedWriteError("Expected current mode must be opposite of target")
    if device_model != _HARDWARE_MODEL or control_firmware != _CONTROL_FIRMWARE:
        raise SupervisedWriteError("Unverified device profile")
    if not host or not 1 <= int(port) <= 65535:
        raise SupervisedWriteError("Invalid inverter TCP target")

    client = client_factory(host, port=port, timeout=5, retries=0)
    sent = False
    before = None
    try:
        if not await client.connect():
            raise SupervisedWriteError("Unable to connect to inverter")
        before = await _snapshot(client)
        if before.mode != expected_mode:
            raise SupervisedWriteError(
                f"Current mode is {before.mode}, expected {expected_mode}: refusing write")

        # Complete double-read immediately before write; reject app/VPP edits
        # detected between our own preflight snapshots.
        second = await _snapshot(client)
        if second != before:
            raise SupervisedWriteError("Inverter changed since preflight: no write")

        writer = client.write_register
        key = "device_id" if "device_id" in inspect.signature(writer).parameters else "slave"
        # Exactly one write; never retry even when acknowledgement times out.
        sent = True
        response = await writer(address=MODE_ADDR, value=target_mode, **{key: UNIT_ID})
        if response is None or response.isError():
            raise SupervisedWriteError(
                "Mode write not acknowledged; result uncertain. Inspect live "
                "readback and restore using elekeeper if needed; no retry issued")
        # Read twice per check to detect a changing controller/app.
        for check in range(6):
            await sleep(2)
            after = await _snapshot(client)
            if (before.charge_mask != after.charge_mask or
                    before.discharge_mask != after.discharge_mask or
                    before.charge_slots != after.charge_slots or
                    before.discharge_slots != after.discharge_slots or
                    before.fallback != after.fallback):
                raise SupervisedWriteError(
                    "Schedules or fallback changed after mode write; "
                    "inspect elekeeper immediately")
            if after.mode == target_mode:
                return {
                    "status": "VERIFIED_BY_MODBUS",
                    "write_sent": True,
                    "before_mode_raw": expected_mode,
                    "after_mode_raw": target_mode,
                    "schedule_masks_unchanged": True,
                    "fallback_unchanged": True,
                    "verification_checks": check + 1,
                    "message": (
                        f"Inverter reports {after.mode_text}. elekeeper may lag. "
                        "Check for external VPP/controller overrides."),
                }
        raise SupervisedWriteError(
            f"Mode write sent but no confirmed mode {target_mode} within 12 seconds; "
            "check elekeeper and direct readback. Do not repeat command")
    except Exception:
        if sent:
            _LOGGER.exception(
                "Supervised SAJ mode write sent or attempted; state uncertain "
                "until elekeeper and Modbus readback checked")
        raise
    finally:
        client.close()
