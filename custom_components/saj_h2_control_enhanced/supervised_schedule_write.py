"""Opt-in SAJ H2 charging slot-1 time-only live pilot.

This is deliberately *not* a general schedule editor. The owner must invoke
the action explicitly; the inverter must be in Self-consumption (mode 0), and
the entire saved schedules must be the specific baseline tested in eLEKeeper.

One FC06 write at a time with verification between them. A failure after the
first write MAY leave a partially modified schedule. Never retry or roll back
automatically, especially while former VPP access remains possible.

PILOT ONLY: Friday charge 22:00-22:40 -> 21:30-22:00, 6930 W.
Discharge and weekday/power words MUST remain unmodified.
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
CONFIRM = "I AUTHORIZE FRIDAY CHARGE TIME TEST"
OLD_START = 0x1600
OLD_END = 0x1628
NEW_START = 0x151E
NEW_END = 0x1600
CHARGE_START_ADDR = 0x3606
CHARGE_END_ADDR = 0x3607


class ScheduleWriteError(RuntimeError):
    pass


async def read_complete(client):
    reader = client.read_holding_registers
    key = "device_id" if "device_id" in inspect.signature(reader).parameters else "slave"

    async def read(address, count):
        reply = await reader(address=address, count=count, **{key: UNIT_ID})
        if reply is None or reply.isError() or len(reply.registers) != count:
            raise ScheduleWriteError(f"Read failed at {address:#06x}")
        return tuple(reply.registers)

    async def once():
        charge = await read(CHARGE_START, CHARGE_COUNT)
        discharge = await read(DISCHARGE_START, DISCHARGE_COUNT)
        mode = (await read(MODE_ADDR, 1))[0]
        fallback = (await read(FALLBACK_ADDR, 1))[0]
        config = decode_config(charge, discharge, mode, fallback)
        return (charge, discharge, config)
    a, b = await once(), await once()
    if a != b:
        raise ScheduleWriteError("Settings changed during full readback")
    return a


def validate_baseline(snapshot):
    charge, discharge, c = snapshot
    if c.mode != 0 or c.fallback != 1:
        raise ScheduleWriteError(
            "Live schedule pilot requires Self-consumption mode and fallback=1")
    if c.charge_mask != 1 or c.discharge_mask != 1:
        raise ScheduleWriteError("Schedule masks must be [1,1]")
    if (charge[2:5] != (OLD_START, OLD_END, 0x1046) or
        discharge[0:3] != (OLD_START, OLD_END, 0x0432)):
        raise ScheduleWriteError(
            "Schedule differs from owner-verified original: pilot rejected")
    return snapshot


def matches_expected(before, current, *, expected_start, expected_end):
    charge0, discharge0, config0 = before
    charge, discharge, config = current
    expected = list(charge0)
    expected[2] = expected_start
    expected[3] = expected_end
    return (
        charge == tuple(expected)
        and discharge == discharge0
        and config.mode == config0.mode
        and config.fallback == config0.fallback
    )


async def run_friday_charge_time_pilot(
    *, host, port, confirmation, device_model, control_firmware,
    client_factory=AsyncModbusTcpClient, sleep=asyncio.sleep,
):
    if confirmation != CONFIRM:
        raise ScheduleWriteError("Explicit exact confirmation required")
    if device_model != "H2-10K-S3-A" or control_firmware != "v2.018":
        raise ScheduleWriteError("Hardware profile not approved for pilot")
    if not host or type(port) is not int or not 1 <= port <= 65535:
        raise ScheduleWriteError("Invalid Modbus host or port")

    client = client_factory(host, port=port, timeout=5, retries=0)
    attempted = []
    try:
        if not await client.connect():
            raise ScheduleWriteError("Could not connect to inverter")
        baseline = validate_baseline(await read_complete(client))
        # One more complete snapshot directly before first write.
        if await read_complete(client) != baseline:
            raise ScheduleWriteError("Concurrent change: no write")

        writer = client.write_register
        key = "device_id" if "device_id" in inspect.signature(writer).parameters else "slave"

        # First command remains a valid, non-overnight window (21:30-22:40).
        attempted.append(CHARGE_START_ADDR)
        ack = await writer(address=CHARGE_START_ADDR, value=NEW_START,
                           **{key: UNIT_ID})
        if ack is None or ack.isError():
            raise ScheduleWriteError(
                "Start write acknowledgement missing, outcome unknown. "
                "Inspect eLEKeeper/Modbus; DO NOT retry automatically")
        await sleep(1)
        partial = await read_complete(client)
        if not matches_expected(
            baseline, partial, expected_start=NEW_START, expected_end=OLD_END
        ):
            raise ScheduleWriteError(
                "After first write, unexpected inverter change detected; "
                "second write NOT sent. Inspect charging slot 1 in eLEKeeper")

        # Second command: end time -> 22:00; power and days still unchanged.
        attempted.append(CHARGE_END_ADDR)
        ack = await writer(address=CHARGE_END_ADDR, value=NEW_END,
                           **{key: UNIT_ID})
        if ack is None or ack.isError():
            raise ScheduleWriteError(
                "End write acknowledgement missing, outcome unknown. "
                "Inspect eLEKeeper/Modbus; DO NOT retry automatically")
        for attempt in range(6):
            await sleep(2)
            final = await read_complete(client)
            if matches_expected(
                baseline, final, expected_start=NEW_START, expected_end=NEW_END
            ):
                return {
                    "status": "SCHEDULE_VERIFIED_BY_MODBUS",
                    "write_sent": True,
                    "writes_attempted": len(attempted),
                    "changed": "Friday charge slot 1: 22:00-22:40 -> 21:30-22:00",
                    "charge_power_watts_unchanged": 6930,
                    "weekday_unchanged": "Friday",
                    "discharge_unchanged": True,
                    "mode_unchanged": True,
                    "fallback_unchanged": True,
                    "verify_checks": attempt + 1,
                    "message": "Reopen eLEKeeper to confirm; cloud may lag.",
                }
            if not matches_expected(
                baseline, final, expected_start=NEW_START, expected_end=OLD_END
            ):
                raise ScheduleWriteError(
                    "Unrecognized concurrent edit after second write. "
                    "Check both schedules immediately; no retry")
        raise ScheduleWriteError(
            "End time not confirmed; partial change possible. "
            "Check eLEKeeper and Modbus; no retry")
    except Exception:
        if attempted:
            _LOGGER.exception(
                "SAJ charging schedule pilot attempted register writes at %s; "
                "check inverter state before any further action",
                attempted)
        raise
    finally:
        client.close()
