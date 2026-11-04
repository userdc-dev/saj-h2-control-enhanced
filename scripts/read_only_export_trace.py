#!/usr/bin/env python3
"""Read-only SAJ H2 site-export logger for investigating day/night behavior.

Only Modbus FC03 holding-register reads are used. NO writes, TOU changes,
power commands, or automatic curtailment. This is observational evidence,
NOT proof of the allowed network export limit or a curtailment setting.

Run from the same environment that has pymodbus installed:
  python scripts/read_only_export_trace.py --host INVERTER_IP --samples 6 --interval 20
"""
from __future__ import annotations

import argparse
from datetime import datetime
import inspect
import time

# Conservatively read only established blocks. Do not scan unknown registers.
READ_BLOCKS = (
    ("mode", 0x3647, 1),
    ("anti_reflux", 0x365A, 3),
    ("battery", 0x406D, 3),
    ("flow", 0x40A0, 14),
    ("meter_a", 0xA03D, 18),
)


def signed16(raw: int) -> int:
    if type(raw) is not int or not 0 <= raw <= 0xFFFF:
        raise ValueError("A Modbus word must be a 16-bit unsigned integer")
    return raw if raw < 32768 else raw - 65536


def _read_block(client, address: int, count: int, unit_id: int) -> list[int]:
    method = client.read_holding_registers
    parameters = inspect.signature(method).parameters
    # pymodbus 3.x renamed 'slave' to 'device_id'.
    if "device_id" in parameters:
        kw = {"device_id": unit_id}
    elif "slave" in parameters:
        kw = {"slave": unit_id}
    else:
        raise ValueError("Unsupported Modbus read signature")
    response = method(address=address, count=count, **kw)
    if response is None or response.isError():
        raise ValueError(f"Read returned an error at 0x{address:04X}")
    words = getattr(response, "registers", None)
    if not isinstance(words, (list, tuple)) or len(words) != count:
        raise ValueError(f"Wrong register count at 0x{address:04X}")
    if any(type(w) is not int or not 0 <= w <= 65535 for w in words):
        raise ValueError(f"Invalid word at 0x{address:04X}")
    return list(words)


def take_snapshot(client, *, unit_id=1, timestamp=None):
    """One set of non-atomic, bounded reads; missing data stays unavailable."""
    result = {
        "timestamp": timestamp or datetime.now().astimezone().isoformat(),
        "errors": {},
        "mode_raw": None,
        "anti_reflux_mode_raw": None,
        "anti_reflux_power_raw": None,
        "soc_percent": None,
        "battery_temp_c": None,
        "battery_inverter_w": None,
        "solar_w": None,
        "house_w": None,
        "battery_aggregate_w": None,
        "site_grid_w": None,
        "meter_grid_w": None,
        "meter_difference_w": None,
        "export_w": None,
    }
    for name, address, count in READ_BLOCKS:
        try:
            values = _read_block(client, address, count, unit_id)
            if name == "mode":
                result["mode_raw"] = values[0]
            elif name == "anti_reflux":
                result["anti_reflux_power_raw"] = values[0]
                result["anti_reflux_mode_raw"] = values[2]
            elif name == "battery":
                # Decode to local variables first. A bad SOC value must not
                # leave a misleading partially accepted battery block.
                inverter_w = signed16(values[0])
                temperature_c = signed16(values[1]) / 10
                raw_soc = values[2]
                if raw_soc > 10000:
                    raise ValueError("SOC outside the documented 0–100% range")
                result["battery_inverter_w"] = inverter_w
                result["battery_temp_c"] = temperature_c
                result["soc_percent"] = raw_soc / 100
            elif name == "flow":
                result["house_w"] = signed16(values[0])
                result["solar_w"] = signed16(values[5])
                result["battery_aggregate_w"] = signed16(values[6])
                result["site_grid_w"] = signed16(values[13])
                result["export_w"] = max(0, -result["site_grid_w"])
            elif name == "meter_a":
                meter_phase_w = [signed16(values[i]) for i in (2, 8, 14)]
                result["meter_grid_w"] = sum(meter_phase_w)
        except (Exception,) as exc:
            # Never reuse old telemetry when a read fails.
            result["errors"][name] = f"{type(exc).__name__}: {exc}"
    if result["site_grid_w"] is not None and result["meter_grid_w"] is not None:
        result["meter_difference_w"] = (
            result["site_grid_w"] - result["meter_grid_w"]
        )
    return result


def _show(v, unit="", decimals=0):
    if v is None:
        return "unknown"
    return f"{v:.{decimals}f}{unit}"


def format_snapshot(s):
    status = (
        "match" if s["meter_difference_w"] is not None
        and abs(s["meter_difference_w"]) <= 200
        else "mismatch/unavailable"
    )
    # These blocks are read sequentially, not atomically; a mismatched
    # meter could simply reflect a rapidly changing house or PV load.
    return (
        f'{s["timestamp"]} | PV {_show(s["solar_w"],"W")} | '
        f'home {_show(s["house_w"],"W")} | '
        f'battery {_show(s["battery_aggregate_w"],"W")} | '
        f'SOC {_show(s["soc_percent"],"%",2)} | '
        f'temp {_show(s["battery_temp_c"],"C",1)} | '
        f'net-grid {_show(s["site_grid_w"],"W")} | '
        f'export {_show(s["export_w"],"W")} | '
        f'meter {_show(s["meter_grid_w"],"W")} | '
        f'meter check {status} | '
        f'mode {s["mode_raw"]} | anti-reflux {s["anti_reflux_mode_raw"]} | '
        f'read-errors {",".join(s["errors"]) if s["errors"] else "none"}'
    )


def summarize(samples):
    valid = [s["export_w"] for s in samples if s["export_w"] is not None]
    if not valid:
        return "No verified export readings; cannot analyse export behavior."
    return (
        f"Observed export min/mean/max: {min(valid):.0f} / "
        f"{sum(valid)/len(valid):.0f} / {max(valid):.0f} W "
        f"({len(valid)}/{len(samples)} samples). "
        "This measures actual export; it does NOT reveal an approved SAPN "
        "limit, prove an export cap, or demonstrate PV curtailment."
    )


def run_trace(client, *, samples=6, interval=20, unit_id=1, sleep=time.sleep):
    if type(samples) is not int or not 1 <= samples <= 12:
        raise ValueError("Samples must be between 1 and 12")
    if type(interval) not in (int, float) or not 10 <= interval <= 120:
        raise ValueError("Interval must be 10–120 seconds")
    print("SAJ H2 EXPORT TRACE — READ ONLY; NO INVERTER WRITES")
    print("WARNING: sample blocks are sequential, not simultaneous.")
    records = []
    for index in range(samples):
        sample = take_snapshot(client, unit_id=unit_id)
        records.append(sample)
        print(f"[{index+1}/{samples}] {format_snapshot(sample)}", flush=True)
        if index != samples - 1:
            sleep(interval)
    print(summarize(records))
    print("End of read-only trace. No mode, TOU, export or BMS change made.")
    return records


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", required=True, help="Inverter LAN IP")
    parser.add_argument("--port", type=int, default=502)
    parser.add_argument("--unit-id", type=int, default=1)
    parser.add_argument("--samples", type=int, default=6)
    parser.add_argument("--interval", type=int, default=20, help="Seconds")
    args = parser.parse_args(argv)
    if not 1 <= args.samples <= 12 or not 10 <= args.interval <= 120:
        parser.error("Use 1–12 samples and an interval of 10–120 seconds")
    if not 1 <= args.unit_id <= 247 or not 1 <= args.port <= 65535:
        parser.error("Invalid Modbus unit ID or port")
    # Import only for live use; test suite runs with a fake read-only client.
    from pymodbus.client import ModbusTcpClient

    client = ModbusTcpClient(args.host, port=args.port, timeout=5, retries=0)
    try:
        if not client.connect():
            print("Cannot reach inverter; no measurements collected.")
            return 2
        run_trace(client, samples=args.samples, interval=args.interval,
                  unit_id=args.unit_id)
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
