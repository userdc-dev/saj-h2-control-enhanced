"""Explicitly supervised, one-shot SAJ H2 mode experiment.

Only targets raw 1 (Time-of-Use) when current raw mode is 0. The user
must manually invoke the HA action with an exact confirmation phrase.
This module is NOT imported by any polling path or dashboard.

Only write: Modbus function 06, 0x3647=1. Never write schedules/fallback.
No automatic retry or rollback because a VPP/eLEKeeper may act concurrently.
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
CONFIRM_PHRASE = "I AUTHORIZE ONE TOU MODE WRITE"
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
        if result.charge_mask != 1 or result.discharge_mask != 1:
            raise SupervisedWriteError(
                "Pilot limited to original one-charge/one-discharge schedule masks")
        if len(result.summary("charge")) != 1 or len(result.summary("discharge")) != 1:
            raise SupervisedWriteError("Invalid active slot count")
        # Pilot is additionally bound to the exact schedules the owner
        # restored and previously confirmed. Any new/edited active schedule
        # requires an entirely new review rather than activating by surprise.
        c = result.charge_slots[0]
        d = result.discharge_slots[0]
        if not (c.enabled and c.start == "22:00" and c.end == "22:40"
                and c.day_mask == 16 and c.power_percent == 70
                and d.enabled and d.start == "22:00" and d.end == "22:40"
                and d.day_mask == 4 and d.power_percent == 50):
            raise SupervisedWriteError(
                "Active schedules differ from owner-verified Friday charge "
                "and Wednesday discharge: no write")
        return result

    first = await once()
    second = await once()
    if first != second:
        raise SupervisedWriteError("Inverter settings changed during verification")
    return second


async def run_supervised_tou_test(
    *, host, port, confirmed_phrase, expected_mode,
    device_model, control_firmware,
    sleep=asyncio.sleep, client_factory=AsyncModbusTcpClient,
):
    """One write at most, preceded by two complete schedule snapshots.

    Returns a response compatible with HA service action response.
    Only an actual HA user action with the exact phrase can invoke this.
    """
    if confirmed_phrase != CONFIRM_PHRASE:
        raise SupervisedWriteError("Exact confirmation phrase required")
    if expected_mode != 0:
        raise SupervisedWriteError("This pilot only switches 0 -> 1")
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
        if before.mode != 0:
            raise SupervisedWriteError(
                f"Current mode is {before.mode}, expected 0: refusing write")

        # Complete double-read immediately before write; reject app/VPP edits
        # detected between our own preflight snapshots.
        second = await _snapshot(client)
        if second != before:
            raise SupervisedWriteError("Inverter changed since preflight: no write")

        writer = client.write_register
        key = "device_id" if "device_id" in inspect.signature(writer).parameters else "slave"
        # Exactly one write; never retry even when acknowledgement times out.
        sent = True
        response = await writer(address=MODE_ADDR, value=1, **{key: UNIT_ID})
        if response is None or response.isError():
            raise SupervisedWriteError(
                "Mode write not acknowledged; result uncertain. Inspect live "
                "readback and restore using eLEKeeper if needed; no retry issued")
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
                    "inspect eLEKeeper immediately")
            if after.mode == 1:
                return {
                    "status": "VERIFIED_BY_MODBUS",
                    "write_sent": True,
                    "before_mode_raw": 0,
                    "after_mode_raw": 1,
                    "schedule_masks_unchanged": True,
                    "fallback_unchanged": True,
                    "verification_checks": check + 1,
                    "message": (
                        "Inverter reports Time-of-Use. eLEKeeper may lag. "
                        "Check for external VPP/controller overrides."),
                }
        raise SupervisedWriteError(
            "Mode write sent but no confirmed mode 1 within 12 seconds; "
            "check eLEKeeper and direct readback. Do not repeat command")
    except Exception:
        if sent:
            _LOGGER.exception(
                "Supervised SAJ mode write sent or attempted; state uncertain "
                "until eLEKeeper and Modbus readback checked")
        raise
    finally:
        client.close()
