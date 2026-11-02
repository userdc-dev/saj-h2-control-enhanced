"""Pure forecast calculations — no Home Assistant dependencies.

Open-Meteo's global_tilted_irradiance is a preceding-hour average.
Its timeformat=unixtime timestamps denote the END of the interval in UTC.
We index each forecast by that ending UTC hour, then convert to local dates.
"""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

# SolarCast Android starting panel layout, editable in this file for now.
# Panel azimuth is compass degrees clockwise from NORTH.
PANEL_GROUPS = (
    (9, 440, 29, 25),
    (15, 440, 27, 25),
    (6, 440, 299, 25),
)
SYSTEM_EFFICIENCY = 0.87
INVERTER_AC_KW = 10.0  # AC output limit, NOT a cap on PV generation
BATTERY_DC_CHARGE_KW = 10.0  # illustrative charge-side ceiling; verify hardware
FORECAST_DAYS = 7
MIN_LEARNING_COVERAGE_SECONDS = 2700  # >=45 minutes of actual observation
MAX_HOURLY_LEARNING_CLOUD = 25  # learn shading on comparatively clear hours
MIN_LEARNING_EXPECTED_KWH = 0.7
MIN_LEARNING_SOC_FOR_POSSIBLE_CURTAILMENT = 97

def api_azimuth(compass_degrees):
    """Open-Meteo uses south-zero, east-negative, west-positive."""
    if not 0 <= compass_degrees <= 360:
        raise ValueError("Panel azimuth must be in 0..360 degrees")
    return ((compass_degrees - 180 + 180) % 360) - 180

def validate_groups(groups):
    for count, watt, azimuth, tilt in groups:
        if not (0 < count <= 100 and 0 < watt <= 800):
            raise ValueError("Invalid panel count or wattage")
        if not (0 <= azimuth <= 360 and 0 <= tilt <= 90):
            raise ValueError("Invalid azimuth or tilt")

def hour_records(weather_series, groups=PANEL_GROUPS, efficiency=SYSTEM_EFFICIENCY,
                 hourly_factors=None, timezone_name='Australia/Adelaide'):
    """Return UTC interval end -> total panel-side hourly forecast in kWh.

    No 10 kW AC clipping: PV may feed simultaneous AC loads and DC battery charging.
    This predicts panel energy, NOT guaranteed delivered AC or chargeable DC.

    All groups MUST have matching UTC timestamps; incomplete hours are omitted,
    not silently replaced with zero.
    """
    validate_groups(groups)
    if len(weather_series) != len(groups):
        raise ValueError("One forecast irradiance series needed per group")
    if not 0 < efficiency <= 1:
        raise ValueError("Invalid forecast system parameters")
    maps = []
    for series in weather_series:
        times = series.get("time", [])
        gti = series.get("global_tilted_irradiance", [])
        clouds = series.get("cloud_cover", [])
        if not (len(times) == len(gti) == len(clouds)):
            raise ValueError("Open-Meteo series length mismatch")
        maps.append({int(t): (g, c) for t, g, c in zip(times, gti, clouds)})
    common = sorted(set.intersection(*(set(series) for series in maps)))
    result = {}
    for end_epoch in common:
        kw = 0.0
        clouds = []
        valid = True
        for (count, watts, _, _), series in zip(groups, maps):
            gti, cloud = series[end_epoch]
            if gti is None or cloud is None or gti < 0 or cloud < 0 or cloud > 100:
                valid = False
                break
            kw += count * watts / 1000 * gti / 1000
            clouds.append(float(cloud))
        if not valid:
            continue
        kw = max(0, kw * efficiency)  # estimated total PV-side power; not AC export
        local_slot = datetime.fromtimestamp(end_epoch - 1, timezone.utc).astimezone(ZoneInfo(timezone_name)).hour
        factor = (hourly_factors or {}).get(str(local_slot), 1.0)
        if not 0.65 <= float(factor) <= 1.15:
            factor = 1.0
        result[end_epoch] = {
            "base_kwh": round(kw, 4),
            "kwh": round(kw * float(factor), 4),
            "cloud": round(sum(clouds) / len(clouds)),
        }
    return result

def day_summaries(hours, timezone_name, now_utc):
    tz = ZoneInfo(timezone_name)
    current_day = now_utc.astimezone(tz).date()
    totals, remaining = {}, {}
    for end, item in hours.items():
        start_dt = datetime.fromtimestamp(end - 3600, timezone.utc).astimezone(tz)
        date_key = start_dt.date().isoformat()
        totals[date_key] = totals.get(date_key, 0.0) + item["kwh"]
        # The current interval is prorated by its remaining portion.
        fractional = min(1.0, max(0.0, (end - now_utc.timestamp()) / 3600.0))
        remaining[date_key] = remaining.get(date_key, 0.0) + item["kwh"] * fractional
    dates = [(current_day + timedelta(days=i)).isoformat() for i in range(FORECAST_DAYS)]
    return {
        "daily": [{"date": day, "kwh": round(totals.get(day, 0), 2)} for day in dates],
        "remaining_today": round(remaining.get(current_day.isoformat(), 0), 2),
    }

def learn_factor(previous, observed_kwh, expected_kwh, cloud, coverage_seconds,
                 battery_soc_peak=None):
    """Conservative adaptation ONLY on clear, representative daylight hours.

    Lower readings aren't evidence of shade or curtailment by themselves.
    Do not learn potential curtailment at nearly full battery; otherwise
    undershooting weather forecasts could incorrectly suppress later forecasts.
    """
    if coverage_seconds < MIN_LEARNING_COVERAGE_SECONDS:
        return None
    if cloud is None or cloud > MAX_HOURLY_LEARNING_CLOUD:
        return None
    if expected_kwh is None or expected_kwh < MIN_LEARNING_EXPECTED_KWH:
        return None
    if observed_kwh is None or observed_kwh < 0:
        return None
    if battery_soc_peak is not None and battery_soc_peak >= MIN_LEARNING_SOC_FOR_POSSIBLE_CURTAILMENT:
        return None
    ratio = max(0.65, min(1.15, observed_kwh / expected_kwh))
    previous = max(0.65, min(1.15, float(previous)))
    return round(max(0.65, min(1.15, previous * 0.85 + ratio * 0.15)), 4)
