"""User-editable, read-only PV forecast for SAJ TOU dashboard.

Only requests weather from Open-Meteo. Never connects to inverter or sends
Modbus writes. Uses its own HA config-entry options, preserving Safe Monitor.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
import logging
from zoneinfo import ZoneInfo

from aiohttp import ClientTimeout
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
DEFAULT_GROUPS = [
    {"count": 9, "watts": 440, "azimuth": 29, "tilt": 25},
    {"count": 15, "watts": 440, "azimuth": 27, "tilt": 25},
    {"count": 6, "watts": 440, "azimuth": 299, "tilt": 25},
]
DEFAULT_EFFICIENCY = 87
DEFAULT_AC_LIMIT = 10.0


def settings_for(entry):
    opts = entry.options
    return {
        "groups": [dict(g) for g in opts.get("forecast_groups", DEFAULT_GROUPS)],
        "efficiency": opts.get("forecast_efficiency", DEFAULT_EFFICIENCY),
        "ac_limit_kw": opts.get("forecast_ac_limit_kw", DEFAULT_AC_LIMIT),
        "configured": bool(opts.get("forecast_configured", False)),
    }


def validate_settings(groups, efficiency, ac_limit_kw):
    if not isinstance(groups, list) or not 1 <= len(groups) <= 8:
        raise ValueError("Enter between 1 and 8 groups")
    clean = []
    for i, item in enumerate(groups, 1):
        if not isinstance(item, dict):
            raise ValueError(f"Group {i} must be an object")
        try:
            values = [float(item[k]) for k in ("count", "watts", "azimuth", "tilt")]
        except (TypeError, ValueError, KeyError) as exc:
            raise ValueError(f"Group {i} has invalid or missing values") from exc
        count, watts, azimuth, tilt = values
        if (not count.is_integer() or not 1 <= count <= 100 or
                not 1 <= watts <= 800 or not 0 <= azimuth <= 360 or
                not 0 <= tilt <= 90):
            raise ValueError(f"Group {i}: count 1–100, watts 1–800, azimuth 0–360, tilt 0–90")
        clean.append({"count": int(count), "watts": watts,
                      "azimuth": azimuth, "tilt": tilt})
    try:
        efficiency, ac_limit_kw = float(efficiency), float(ac_limit_kw)
    except (TypeError, ValueError) as exc:
        raise ValueError("Efficiency and AC limit must be numbers") from exc
    if not 1 <= efficiency <= 100 or not 0.5 <= ac_limit_kw <= 100:
        raise ValueError("Efficiency 1–100%, AC limit 0.5–100 kW")
    return clean, efficiency, ac_limit_kw


class SajEditableForecast(DataUpdateCoordinator):
    """Weather estimates distinct from inverter readback and Safe Monitor data."""

    def __init__(self, hass, entry):
        super().__init__(hass, _LOGGER, name="SAJ editable solar forecast",
                         update_interval=timedelta(minutes=60))
        self.entry = entry
        self._forecast_hours = {}
        self._fetched_at = None
        self._previous_settings = None

    async def _group_weather(self, session, group):
        # Open-Meteo azimuth is -180..180 degrees relative to due south.
        azimuth = ((group["azimuth"] - 180 + 180) % 360) - 180
        params = {
            "latitude": self.hass.config.latitude,
            "longitude": self.hass.config.longitude,
            "hourly": "global_tilted_irradiance,cloud_cover",
            "tilt": group["tilt"],
            "azimuth": azimuth,
            "timezone": "UTC",
            "timeformat": "unixtime",
            "forecast_days": 8,
        }
        async with session.get(FORECAST_URL, params=params,
                               timeout=ClientTimeout(total=20)) as response:
            response.raise_for_status()
            data = await response.json()
        hourly = data.get("hourly") or {}
        timestamps = hourly.get("time") or []
        irradiance = hourly.get("global_tilted_irradiance") or []
        clouds = hourly.get("cloud_cover") or []
        if not (len(timestamps) == len(irradiance) == len(clouds)):
            raise ValueError("Weather response has inconsistent hourly values")
        return {int(t): (v, c) for t, v, c in zip(timestamps, irradiance, clouds)}

    async def _async_update_data(self):
        settings = settings_for(self.entry)
        groups, efficiency, ac_limit = validate_settings(
            settings["groups"], settings["efficiency"], settings["ac_limit_kw"])
        settings_key = (str(groups), efficiency, ac_limit)
        if self._previous_settings != settings_key:
            self._forecast_hours = {}
        session = async_get_clientsession(self.hass)
        try:
            series = await asyncio.gather(
                *(self._group_weather(session, group) for group in groups))
            common = sorted(set.intersection(*(set(part) for part in series)))
            if len(common) < 24:
                raise ValueError("Fewer than 24 common weather forecast hours")
            hours = {}
            for end in common:
                wh = 0.0
                cloud_values = []
                for group, data in zip(groups, series):
                    irradiance, cloud = data[end]
                    if (irradiance is None or cloud is None or
                            not 0 <= irradiance <= 1500 or not 0 <= cloud <= 100):
                        break
                    wh += group["count"] * group["watts"] * irradiance / 1000
                    cloud_values.append(cloud)
                else:
                    # kWh over a one-hour sample, estimated on PV side.
                    # Do not cap by AC inverter nameplate: DC charging may coexist.
                    hours[end] = {"kwh": round(wh * efficiency / 100 / 1000, 4),
                                  "cloud": round(sum(cloud_values) / len(cloud_values))}
            if len(hours) < 24:
                raise ValueError("Insufficient valid weather samples")
            self._forecast_hours = hours
            self._previous_settings = settings_key
            self._fetched_at = datetime.now(timezone.utc)
        except Exception as exc:
            if not self._forecast_hours:
                raise UpdateFailed(f"Editable forecast unavailable: {exc}") from exc
            _LOGGER.warning("Weather refresh failed; retaining last forecast: %s", exc)
        return self._make_snapshot(settings)

    def _make_snapshot(self, settings):
        now = datetime.now(timezone.utc)
        tz_name = self.hass.config.time_zone or "Australia/Adelaide"
        tz = ZoneInfo(tz_name)
        today = now.astimezone(tz).date()
        totals, remaining = {}, {}
        samples = []
        for end, item in sorted(self._forecast_hours.items()):
            start = datetime.fromtimestamp(end - 3600, timezone.utc)
            local = start.astimezone(tz)
            day = local.date().isoformat()
            totals[day] = totals.get(day, 0.0) + item["kwh"]
            fraction = max(0.0, min(1.0, (end - now.timestamp()) / 3600))
            remaining[day] = remaining.get(day, 0.0) + item["kwh"] * fraction
            if local.date() == today:
                samples.append({"hour": local.strftime("%H:%M"),
                                "kwh": round(item["kwh"], 2),
                                "cloud": item["cloud"]})
        daily = [{"date": (today + timedelta(days=i)).isoformat(),
                  "kwh": round(totals.get((today + timedelta(days=i)).isoformat(), 0), 2)}
                 for i in range(7)]
        return {
            "daily": daily,
            "hourly_today": samples,
            "remaining_today": round(remaining.get(today.isoformat(), 0), 2),
            "today": daily[0]["kwh"],
            "tomorrow": daily[1]["kwh"],
            "week": round(sum(v["kwh"] for v in daily), 2),
            "updated": self._fetched_at.isoformat() if self._fetched_at else None,
            "settings": settings,
            "model": "Open-Meteo tilted irradiance; PV-side estimate; no AC clipping",
            "note": ("AC limit is displayed for system reference, not applied as a "
                     "PV production cap because DC battery charging can coexist with AC output."),
        }

    def on_live_update(self):
        """Recalculate partial-day remaining based on clock without new API calls."""
        if self._forecast_hours:
            self.async_set_updated_data(self._make_snapshot(settings_for(self.entry)))
