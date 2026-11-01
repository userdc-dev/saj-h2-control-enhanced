"""User-triggered, supervised SAJ H2 outside-TOU fallback control.

This is a distinct Modbus single-register operation (0x365F). Observed
readback: 0 = Standby, 1 = Self-consumption. Standby can alter battery use
outside scheduled periods; dashboard requires user confirmation to select it.

Double-read complete schedule blocks/mode/fallback before writing. Write at
most once using FC06, no retry or automatic rollback, and verify that ONLY
the requested fallback register changed. A lost acknowledgement is ambiguous.
"""
import asyncio
import inspect
import logging

from pymodbus.client import AsyncModbusTcpClient

from .const import UNIT_ID
from .tou_protocol import (
    CHARGE_START, CHARGE_COUNT, DISCHARGE_START, DISCHARGE_COUNT,
    MODE_ADDR, FALLBACK_ADDR, decode_config,
)

_LOGGER = logging.getLogger(__name__)
_DEVICE_MODEL = "H2-10K-S3-A"
_FIRMWARE = "v2.018"
_STANDBY_CONFIRM = "I CONFIRM STANDBY OUTSIDE TOU"


class FallbackWriteError(RuntimeError):
    """An unsafe, conflicting, or unverified fallback operation."""


async def _double_snapshot(client):
    method = client.read_holding_registers
    key = "device_id" if "device_id" in inspect.signature(method).parameters else "slave"

    async def read(addr, count):
        response = await method(address=addr, count=count, **{key: UNIT_ID})
        if response is None or response.isError() or len(response.registers) != count:
            raise FallbackWriteError(f"Invalid Modbus read at {addr:#06x}")
        return tuple(response.registers)

    async def once():
        charge = await read(CHARGE_START, CHARGE_COUNT)
        discharge = await read(DISCHARGE_START, DISCHARGE_COUNT)
        mode = (await read(MODE_ADDR, 1))[0]
        fallback = (await read(FALLBACK_ADDR, 1))[0]
        config = decode_config(charge, discharge, mode, fallback)
        if config.mode not in (0, 1):
            raise FallbackWriteError("Unsupported operating mode; no write")
        if config.fallback not in (0, 1):
            raise FallbackWriteError("Unsupported fallback code; no write")
        for group in (config.charge_slots, config.discharge_slots):
            for slot in group:
                if slot.enabled and (
                    not 1 <= slot.power_percent <= 100
                    or not 1 <= slot.day_mask <= 127
                    or slot.start == "unknown" or slot.end == "unknown"
                ):
                    raise FallbackWriteError("Active schedule invalid; no write")
        return charge, discharge, config

    first, second = await once(), await once()
    if first != second:
        raise FallbackWriteError("Device configuration changed during readback")
    return second


async def run_fallback_control(
    *, host, port, target, expected_fallback, expected_mode,
    standby_confirmation, device_model, control_firmware,
    client_factory=AsyncModbusTcpClient, sleep=asyncio.sleep,
):
    """At most one FC06 to 0x365F, then verify unchanged mode/schedules."""
    if type(target) is not int or target not in (0, 1):
        raise FallbackWriteError("Only Standby or Self-consumption supported")
    if type(expected_fallback) is not int or expected_fallback != 1 - target:
        raise FallbackWriteError("Invalid previously observed fallback")
    if type(expected_mode) is not int or expected_mode not in (0, 1):
        raise FallbackWriteError("Unsupported previously observed operating mode")
    if target == 0 and standby_confirmation != _STANDBY_CONFIRM:
        raise FallbackWriteError("Standby requires explicit confirmation")
    if device_model != _DEVICE_MODEL or control_firmware != _FIRMWARE:
        raise FallbackWriteError("Hardware profile not approved for fallback writes")
    if not host or type(port) is not int or not 1 <= port <= 65535:
        raise FallbackWriteError("Invalid inverter connection details")

    client = client_factory(host, port=port, timeout=5, retries=0)
    sent = False
    try:
        if not await client.connect():
            raise FallbackWriteError("Could not connect to inverter")
        before = await _double_snapshot(client)
        if before[2].mode != expected_mode or before[2].fallback != expected_fallback:
            raise FallbackWriteError("Mode/fallback changed since dashboard readback")
        if await _double_snapshot(client) != before:
            raise FallbackWriteError("Device changed since preflight; no write")

        writer = client.write_register
        key = "device_id" if "device_id" in inspect.signature(writer).parameters else "slave"
        sent = True
        ack = await writer(address=FALLBACK_ADDR, value=target, **{key: UNIT_ID})
        if ack is None or ack.isError():
            raise FallbackWriteError(
                "Fallback write acknowledgement missing: state unknown. "
                "Inspect live readback/elekeeper before another command")
        for check in range(6):
            await sleep(2)
            after = await _double_snapshot(client)
            if (
                after[0] != before[0]
                or after[1] != before[1]
                or after[2].mode != before[2].mode
            ):
                raise FallbackWriteError(
                    "Mode or schedules changed after fallback command: "
                    "check elekeeper; no retry")
            if after[2].fallback == target:
                return {
                    "status": "FALLBACK_VERIFIED_BY_MODBUS",
                    "write_sent": True,
                    "before_fallback_raw": expected_fallback,
                    "after_fallback_raw": target,
                    "after_fallback": "Standby" if target == 0 else "Self-consumption",
                    "mode_unchanged": True,
                    "charge_and_discharge_unchanged": True,
                    "verification_checks": check + 1,
                    "message": "Outside-TOU behaviour verified by live Modbus. elekeeper may lag.",
                }
            if after[2].fallback != expected_fallback:
                raise FallbackWriteError("Unexpected fallback code after write")
        raise FallbackWriteError(
            "Fallback write sent, but readback did not confirm the target. "
            "Inspect elekeeper/Modbus; do not retry")
    except Exception:
        if sent:
            _LOGGER.exception(
                "SAJ outside-TOU fallback write attempted. "
                "Device state may be uncertain until inspected")
        raise
    finally:
        client.close()
