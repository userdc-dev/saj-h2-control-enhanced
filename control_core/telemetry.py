"""Map existing SAJ safe-monitor entities into validated control input.

This pure Python module imports no HA or Modbus packages. There is deliberately
NO write transport. HA integrations may adapt hass.states objects to these
plain immutable observations later.

IMPORTANT: last_changed is not freshness. A value can remain unchanged for
hours despite healthy polls, or remain stale after a failed poll. Use the
read-only coordinator's successful-poll heartbeat when available. This first
iteration refuses control without a verified heartbeat.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
import math
from typing import Mapping

BASE = "sensor.saj_h2_safe_monitor_"

ENTITY_IDS = {
    "soc_pct": BASE + "battery_state_of_charge",
    "battery_w": BASE + "battery_power",
    "battery_activity": BASE + "battery_activity",
    "mode": BASE + "operating_mode",
    "solar_w": BASE + "total_solar_power",
    "home_w": BASE + "home_consumption",
    "grid_w": BASE + "grid_power_raw_signed",
    "stored_kwh": BASE + "estimated_battery_energy",
    "battery_temp_c": BASE + "battery_temperature",
    "battery_voltage_v": BASE + "battery_voltage",
}
# NO forecasts, monthly totals, or generated dashboard strings can authorize
# battery control. Only validated raw monitor telemetry is eligible.

@dataclass(frozen=True)
class Observation:
    value: str
    unit: str | None = None

@dataclass(frozen=True)
class Snapshot:
    captured_at: datetime
    soc_pct: float
    battery_w: float
    battery_activity: str
    mode: str
    solar_w: float
    home_w: float
    grid_w: float
    stored_kwh: float
    battery_temp_c: float
    battery_voltage_v: float
    poll_verified: bool
    poll_age_s: float | None

@dataclass(frozen=True)
class TelemetryResult:
    snapshot: Snapshot | None
    problems: tuple[str, ...]
    ready_for_writes: bool = False  # hard-locked: no authorized write transport

UNAVAILABLE = {"unknown", "unavailable", "none", "", "nan", "inf", "-inf"}

def _number(entry: Observation | None, label: str, unit: str, lo: float, hi: float, issues: list[str]) -> float:
    if entry is None:
        issues.append(f"{label}: missing entity")
        return 0.0
    if entry.unit not in (unit, None):
        issues.append(f"{label}: unexpected units {entry.unit!r}")
        return 0.0
    if entry.value.strip().lower() in UNAVAILABLE:
        issues.append(f"{label}: unavailable")
        return 0.0
    try:
        value = float(entry.value)
    except (ValueError, TypeError):
        issues.append(f"{label}: non-numeric")
        return 0.0
    if not math.isfinite(value) or not lo <= value <= hi:
        issues.append(f"{label}: out of bounds")
        return 0.0
    return value

def parse_snapshot(
    states: Mapping[str, Observation],
    *,
    now: datetime,
    verified_last_poll: datetime | None = None,
    allowed_poll_age_s: float = 35,
) -> TelemetryResult:
    """Parse a synchronized view. Never turns missing data into valid zeroes."""
    if now.tzinfo is None:
        raise ValueError("now must be timezone aware")
    problems: list[str] = []
    values = {}
    for key, unit, lo, hi in (
        ("soc_pct", "%", 0, 100),
        ("battery_w", "W", -30000, 30000),
        ("solar_w", "W", 0, 50000),
        ("home_w", "W", 0, 50000),
        ("grid_w", "W", -30000, 30000),
        ("stored_kwh", "kWh", 0, 40),
        ("battery_temp_c", "°C", -30, 90),
        ("battery_voltage_v", "V", 0, 1000),
    ):
        values[key] = _number(states.get(ENTITY_IDS[key]), key, unit, lo, hi, problems)
    for key in ("battery_activity", "mode"):
        item = states.get(ENTITY_IDS[key])
        val = item.value.strip() if item else ""
        if val.lower() in UNAVAILABLE:
            problems.append(f"{key}: missing/unavailable")
        values[key] = val
    # Some sensors can be valid for display but not safe for write decisions.
    if values["mode"] not in ("Self-consumption", "Time-of-use"):
        problems.append("mode: unknown or unsafe for control")
    if values["battery_activity"] not in ("Charging", "Discharging", "Idle"):
        problems.append("battery_activity: invalid status")
    if values["soc_pct"] == 0 and values["battery_w"] != 0:
        # Not automatically invalid physically, but needs verified controller limits.
        problems.append("SOC depleted while battery power nonzero")
    age = None
    poll_verified = False
    if verified_last_poll is None:
        problems.append("no verified successful-poll heartbeat")
    elif verified_last_poll.tzinfo is None:
        problems.append("heartbeat without timezone")
    else:
        age = (now - verified_last_poll).total_seconds()
        poll_verified = 0 <= age <= allowed_poll_age_s
        if not poll_verified:
            problems.append(f"heartbeat stale or in future: {age:.1f}s")
    if problems:
        return TelemetryResult(snapshot=None, problems=tuple(problems))
    return TelemetryResult(
        snapshot=Snapshot(captured_at=now, poll_verified=poll_verified, poll_age_s=age, **values),
        problems=(),
    )

def display_diagnostics(result: TelemetryResult) -> dict:
    """Information UI can show without accidentally enabling a control button."""
    return {
        "telemetry_valid": result.snapshot is not None,
        "problems": list(result.problems),
        "control_enabled": False,
        "write_transport": "NOT IMPLEMENTED",
    }
