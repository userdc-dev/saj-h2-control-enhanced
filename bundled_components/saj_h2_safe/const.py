"""SAJ H2 read-only sensor definitions and defensive decoders."""
DOMAIN = "saj_h2_safe"
DEFAULT_PORT = 502
DEFAULT_SCAN_INTERVAL = 60
# SAJ app reports 40.00 kWh installed nominal capacity (two battery stacks).
# Energy estimate = displayed SOC * 40.00 / 100; not BMS usable energy.
DEFAULT_BATTERY_CAPACITY_KWH = 40.00

# key: (register address, friendly name, unit, multiplier, signed, min, max)
# Verified against the SAJ app: battery SOC, PV1-3, load, signed grid watts at zero.
SENSORS = {
    "battery_voltage": (0x4069, "Battery voltage", "V", .1, False, 0, 1000),
    "battery_current": (0x406A, "Battery current", "A", .01, True, -500, 500),
    "battery_power": (0x406D, "Battery power", "W", 1, True, -32768, 32767),
    "battery_temperature": (0x406E, "Battery temperature", "°C", .1, True, -40, 100),
    "battery_soc": (0x406F, "Battery state of charge", "%", .01, False, 0, 100),
    "pv1_voltage": (0x4071, "PV1 voltage", "V", .1, False, 0, 1000),
    "pv1_power": (0x4073, "PV1 power", "W", 1, False, 0, 30000),
    "pv2_voltage": (0x4074, "PV2 voltage", "V", .1, False, 0, 1000),
    "pv2_power": (0x4076, "PV2 power", "W", 1, False, 0, 30000),
    "pv3_voltage": (0x4077, "PV3 voltage", "V", .1, False, 0, 1000),
    "pv3_power": (0x4079, "PV3 power", "W", 1, False, 0, 30000),
    "total_pv_power": (None, "Total solar power", "W", 1, False, 0, 90000),
    "home_load_power": (0x40A0, "Home consumption", "W", 1, True, 0, 30000),
    "grid_power": (0x40AD, "Grid power (raw signed)", "W", 1, True, -30000, 30000),
    "grid_import": (None, "Grid import (direction unverified)", "W", 1, False, 0, 30000),
    "grid_export": (None, "Grid export (direction unverified)", "W", 1, False, 0, 30000),
    "battery_stored_energy": (None, "Estimated battery energy", "kWh", 1, False, 0, 100),
    "battery_activity": (None, "Battery activity", None, 1, False, 0, 0),
}
# 32-bit counters: high word first, units 0.01 kWh (see upstream reader).
# Offsets within 0x40BF block for solar and battery.
# 0x40DF block for load and grid energy. Grid energy naming kept as SAJ
# 'sell'/'feed-in' until confirmed with non-zero app import/export values.
ENERGY_GROUPS = {
    "solar": (0x40BF, 0, "Solar"),
    "battery_charge": (0x40BF, 8, "Battery charged"),
    "battery_discharge": (0x40BF, 16, "Battery discharged"),
    "home": (0x40DF, 0, "Home consumed"),
    "grid_sell": (0x40DF, 16, "SAJ grid sell (unverified)"),
    "grid_feed_in": (0x40DF, 24, "SAJ grid feed-in (unverified)"),
}
PERIODS = ("today", "month", "year", "total")
ENERGY_KEYS = {
    f"{group}_{period}": (addr + offset + i * 2, f"{label} {period}")
    for group, (addr, offset, label) in ENERGY_GROUPS.items()
    for i, period in enumerate(PERIODS)
}
# Read-only display labels for this installation.
# Code 3 is called "Off-grid" by the owner, while the upstream integration
# labels AppMode=3 as "Passive". Do not assume those functions are identical.
# This mapping is NEVER used to construct or send Modbus commands.
MODE_LABELS = {
    0: "Self-consumption",
    1: "Time-of-use",
    2: "Backup (avoid)",
    3: "Off-grid / Passive (firmware label unverified; avoid)",
}
# Non-negotiable control policy for a future opt-in write layer:
# no commands may select Backup, Off-grid, or Passive on this installation.
BLOCKED_MODE_CODES = frozenset({2, 3})
def decode(raw, signed, scale, low, high):
    if not isinstance(raw, int) or not 0 <= raw <= 65535:
        return None
    if not signed and raw == 0xFFFF:
        return None
    value = (raw - 65536 if signed and raw & 0x8000 else raw) * scale
    return round(value, 3) if low <= value <= high else None

def decode_energy(high, low):
    if not all(isinstance(x, int) and 0 <= x <= 0xFFFF for x in (high, low)):
        return None
    if high == low == 0xFFFF:
        return None
    result = ((high << 16) | low) / 100
    return round(result, 2) if 0 <= result <= 1_000_000 else None

def aggregate_solar_power(readings):
    values = [readings.get(k) for k in ("pv1_power", "pv2_power", "pv3_power")]
    return None if any(v is None for v in values) else sum(values)

def derived_values(readings, capacity_kwh=DEFAULT_BATTERY_CAPACITY_KWH):
    readings["total_pv_power"] = aggregate_solar_power(readings)
    battery = readings.get("battery_power")
    # Positive battery watts matched discharge in the user's SAJ app.
    readings["battery_activity"] = (
        None if battery is None else
        "Discharging" if battery > 15 else
        "Charging" if battery < -15 else "Idle"
    )
    soc = readings.get("battery_soc")
    readings["battery_stored_energy"] = round(soc * capacity_kwh / 100, 2) if soc is not None and 0 < capacity_kwh <= 100 else None
    grid = readings.get("grid_power")
    # IMPORTANT: polarity inferred, not yet checked with nonzero grid flow.
    readings["grid_import"] = max(grid, 0) if grid is not None else None
    readings["grid_export"] = max(-grid, 0) if grid is not None else None
    return readings
