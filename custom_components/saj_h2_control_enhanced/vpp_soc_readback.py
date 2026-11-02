"""Read-only, fresh battery SOC verification for VPP safety preflight.

The SAJ H2 battery state of charge is the holding register 0x406F in
hundredths of one percent. This mapping is the same as our independently
tested Safe Monitor register profile. Do NOT use an assumed HA entity ID or
stale Recorder data for a safety-critical preflight.

Only Modbus function 03 is used. No writes, SOC overrides or fallbacks.
"""
from __future__ import annotations

import inspect

SOC_REGISTER = 0x406F
SOC_SCALE = 0.01
MIN_RAW_SOC = 0
MAX_RAW_SOC = 10000
# Two direct reads must agree to within 1 percentage point. Significant
# changes or inconsistent frames are treated as unverified, never averaged.
MAX_RAW_DIFFERENCE = 100


class BatterySocReadbackError(ValueError):
    """The battery SOC cannot be safely verified on the inverter."""


async def read_verified_battery_soc(client, *, unit_id=1):
    """Return a fresh, double-read 0..100% SOC or refuse the measurement.

    Use the ALREADY connected control Modbus client, under pilot_lock.
    Supports both pymodbus device_id (new) and slave (older) signatures.
    """
    method = client.read_holding_registers
    params = inspect.signature(method).parameters
    if "device_id" in params:
        kwargs = {"device_id": unit_id}
    else:
        kwargs = {"slave": unit_id}

    async def read_once():
        try:
            response = await method(
                address=SOC_REGISTER, count=1, **kwargs
            )
        except Exception as exc:
            raise BatterySocReadbackError(
                f"SOC read request failed: {type(exc).__name__}"
            ) from exc
        if response is None or response.isError():
            raise BatterySocReadbackError("Inverter SOC read returned an error")
        words = getattr(response, "registers", None)
        if not isinstance(words, (list, tuple)) or len(words) != 1:
            raise BatterySocReadbackError("Invalid SOC register count")
        raw = words[0]
        if type(raw) is not int or not MIN_RAW_SOC <= raw <= MAX_RAW_SOC:
            raise BatterySocReadbackError("SOC is outside 0–100%")
        return raw

    first = await read_once()
    second = await read_once()
    if abs(first - second) > MAX_RAW_DIFFERENCE:
        raise BatterySocReadbackError(
            "Inconsistent inverter SOC readings; safety preflight blocked"
        )
    # Use the latest of two verified samples, not a potentially stale HA
    # cached sensor, and do not infer a value on any error.
    return round(second * SOC_SCALE, 2)
