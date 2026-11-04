#!/usr/bin/env python3
"""One-shot, strictly read-only SAJ H2 site-export control-source fingerprint.

These are KNOWN holding-register reads only (Modbus function 03).
This does NOT expose the SAPN/CSIP-AUS current operating envelope or its
heartbeat, which might live in the manufacturer's communications gateway.
It cannot establish a legal export permission or test inverter control writes.
"""
from __future__ import annotations
from datetime import datetime
import inspect

BLOCKS = (
    ("schedule_flags", 0x3606, 2),
    ("mode", 0x3647, 1),
    ("grid_port_percent", 0x364F, 2),
    ("local_anti_reflux", 0x365A, 3),
    ("grid_port_measurements", 0x4031, 6),
    ("battery", 0x406D, 3),
    ("energy_flows", 0x40A0, 14),
    ("meter_a", 0xA03D, 6),
)


def signed16(word):
    if type(word) is not int or not 0 <= word <= 65535:
        raise ValueError("Not a 16-bit Modbus word")
    return word if word < 32768 else word - 65536


def _read(client, address, count, unit):
    method = client.read_holding_registers
    params = inspect.signature(method).parameters
    if "device_id" in params:
        kw = {"device_id": unit}
    elif "slave" in params:
        kw = {"slave": unit}
    else:
        raise ValueError("Unsupported pymodbus signature")
    response = method(address=address, count=count, **kw)
    if response is None or response.isError():
        raise ValueError("Modbus FC03 returned error")
    data = getattr(response, "registers", None)
    if not isinstance(data, (list, tuple)) or len(data) != count:
        raise ValueError("Incomplete register response")
    if any(type(v) is not int or not 0 <= v <= 65535 for v in data):
        raise ValueError("Invalid response word")
    return tuple(data)


def take_snapshot(client, unit=1):
    raw, errors = {}, {}
    for name, address, count in BLOCKS:
        try:
            raw[name] = _read(client, address, count, unit)
        except Exception as exc:
            errors[name] = f"{type(exc).__name__}: {exc}"
    return raw, errors


def interpret(raw, errors):
    result = {"errors": errors.copy()}
    if "schedule_flags" in raw:
        charge, discharge = raw["schedule_flags"]
        result["charge_mask_raw"] = charge
        result["discharge_mask_raw"] = discharge
    if "mode" in raw:
        result["operating_mode_raw"] = raw["mode"][0]
    if "grid_port_percent" in raw:
        in_percent, out_percent = raw["grid_port_percent"]
        result["grid_input_percent"] = in_percent / 10
        result["grid_output_percent"] = out_percent / 10
    if "local_anti_reflux" in raw:
        power, current, mode = raw["local_anti_reflux"]
        result["local_limit_power_raw"] = power
        result["local_limit_current_raw"] = current
        result["local_anti_reflux_mode_raw"] = mode
    if "grid_port_measurements" in raw:
        words = raw["grid_port_measurements"]
        result["grid_voltage_v"] = words[0] / 10
        result["grid_frequency_hz"] = words[2] / 100
        result["inverter_grid_port_w"] = signed16(words[4])
    if "battery" in raw:
        v = raw["battery"]
        result["battery_temp_c"] = signed16(v[1]) / 10
        if 0 <= v[2] <= 10000:
            result["soc_percent"] = v[2] / 100
        else:
            result["errors"]["battery_soc"] = "SOC outside 0..100%"
    if "energy_flows" in raw:
        v = raw["energy_flows"]
        result["house_w"] = signed16(v[0])
        result["pv_w"] = signed16(v[5])
        result["battery_w"] = signed16(v[6])
        result["site_grid_w"] = signed16(v[13])
        result["export_w"] = max(0, -result["site_grid_w"])
    if "meter_a" in raw:
        result["meter_phase_1_w"] = signed16(raw["meter_a"][2])
    return result


def main():
    from pymodbus.client import ModbusTcpClient
    client = ModbusTcpClient("172.16.1.4", port=502, timeout=5, retries=0)
    print("SAJ H2 CONTROL SOURCE FINGERPRINT — FC03 READ ONLY")
    print(datetime.now().astimezone().isoformat())
    try:
        if not client.connect():
            print("Could not connect; no settings changed")
            return 1
        raw, errors = take_snapshot(client)
        data = interpret(raw, errors)
        for key, value in data.items():
            print(f"{key}: {value}")
        print("NOT exposed here: SAPN dynamic export allowance,")
        print("CSIP-AUS client identity, heartbeat, expiry or fallback cause.")
        print("Comparisons: last known 2026-11-03 daytime 0x365A=1100,")
        print("0x365C=0, and 2026-11-04 grid-port input/output=110%.")
        print("COMPLETED — no inverter writes, mode or settings changed.")
        return 0 if not errors else 2
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
