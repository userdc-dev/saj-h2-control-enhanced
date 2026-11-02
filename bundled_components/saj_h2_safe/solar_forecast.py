"""Weather-driven SAJ solar forecasting with read-only measured-power learning.

Only this module contacts Open-Meteo. It NEVER writes to Modbus or SAJ.
"""
from __future__ import annotations

import asyncio
import logging
from aiohttp import ClientTimeout
from datetime import datetime, timezone, timedelta
from time import monotonic
from zoneinfo import ZoneInfo

from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .solar_model import (
    PANEL_GROUPS, SYSTEM_EFFICIENCY, INVERTER_AC_KW, BATTERY_DC_CHARGE_KW,
    api_azimuth, hour_records, day_summaries, learn_factor,
)

_LOGGER = logging.getLogger(__name__)
URL = "https://api.open-meteo.com/v1/forecast"
ENERGY_SENSORS = {
    "forecast_today": ("Today's solar forecast", "kWh"),
    "forecast_today_outlook": ("Today's solar outlook (actual + remaining)", "kWh"),
    "forecast_remaining": ("Solar forecast remaining today", "kWh"),
    "forecast_tomorrow": ("Tomorrow's solar forecast", "kWh"),
    "forecast_seven_days": ("Next 7 days solar forecast", "kWh"),
    "forecast_next_hour": ("Next hour solar forecast", "kWh"),
}
STATUS_SENSORS = {
    "forecast_learning": "Forecast learning",
    "forecast_updated": "Weather forecast updated",
}
class SajSolarForecastCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, entry, live):
        super().__init__(hass, _LOGGER, name="SAJ Solar Forecast",
                         update_interval=timedelta(minutes=60))
        self.entry = entry
        self.live = live
        self.tz = hass.config.time_zone or "Australia/Adelaide"
        self.store = Store(hass, 1, f"saj_h2_safe_forecast_{entry.entry_id}")
        self.factors = {}
        self.learned_hours = 0
        self.hours = {}
        self.fetched_at = None
        self._hour_end = None
        self._last_sample_epoch = None
        self._last_power = None
        self._hour_kwh = 0.0
        self._hour_coverage = 0.0
        self._hour_soc_peak = 0.0
        self._last_save = 0.0

    async def async_load_history(self):
        try:
            saved = await self.store.async_load() or {}
            self.factors = {
                str(k): float(v) for k, v in saved.get("factors", {}).items()
                if str(k).isdigit() and 0 <= int(k) <= 23 and 0.65 <= float(v) <= 1.15
            }
            self.learned_hours = max(0, int(saved.get("learned_hours", 0)))
        except (ValueError, TypeError, KeyError) as exc:
            _LOGGER.warning("Solar learning data invalid; starting fresh: %s", exc)
            self.factors = {}

    async def _get_group_forecast(self, session, group):
        count, watt, azimuth, tilt = group
        params = {
            "latitude": self.hass.config.latitude,
            "longitude": self.hass.config.longitude,
            "hourly": "global_tilted_irradiance,cloud_cover",
            "tilt": tilt,
            "azimuth": api_azimuth(azimuth),
            "timezone": self.tz,
            "timeformat": "unixtime",
            "forecast_days": 7,
        }
        async with session.get(URL, params=params, timeout=ClientTimeout(total=20)) as response:
            response.raise_for_status()
            data = await response.json()
        hourly = data.get("hourly") or {}
        return {
            "time": hourly.get("time") or [],
            "global_tilted_irradiance": hourly.get("global_tilted_irradiance") or [],
            "cloud_cover": hourly.get("cloud_cover") or [],
        }

    async def _async_update_data(self):
        session = async_get_clientsession(self.hass)
        # Three independent tilted irradiance calls, one per panel orientation.
        try:
            series = await asyncio.gather(
                *(self._get_group_forecast(session, g) for g in PANEL_GROUPS)
            )
            new_hours = hour_records(
                series, hourly_factors=self.factors, timezone_name=self.tz,
                efficiency=SYSTEM_EFFICIENCY,
            )
            if len(new_hours) < 24:
                raise ValueError("Weather forecast has fewer than 24 valid hourly intervals")
            self.hours = new_hours
            self.fetched_at = datetime.now(timezone.utc)
        except Exception as exc:
            # Do not erase a previously good forecast on transient network errors.
            if not self.hours:
                raise UpdateFailed(f"Solar forecast unavailable: {exc}") from exc
            _LOGGER.warning("Weather temporarily unavailable; retaining last forecast: %s", exc)
        return self._make_data()

    def _make_data(self):
        if not self.hours:
            return {}
        now = datetime.now(timezone.utc)
        sums = day_summaries(self.hours, self.tz, now)
        daily = sums["daily"]
        actual = (self.live.data or {}).get("solar_today")
        remaining = sums["remaining_today"]
        current_hour_end = (int(now.timestamp()) // 3600 + 1) * 3600
        # Nearest next full hour AFTER the current one.
        next_hour_end = current_hour_end + 3600
        next_hour = self.hours.get(next_hour_end, {})
        local_time = now.astimezone(ZoneInfo(self.tz))
        hourly_list = []
        for end in sorted(self.hours):
            if current_hour_end <= end < current_hour_end + 24 * 3600:
                item = self.hours[end]
                hourly_list.append({
                    "time": datetime.fromtimestamp(end - 3600, timezone.utc)
                        .astimezone(ZoneInfo(self.tz)).strftime("%a %H:%M"),
                    "kwh": round(item["kwh"], 2),
                    "cloud": item["cloud"],
                })
        return {
            "forecast_today": daily[0]["kwh"],
            "forecast_today_outlook": (round(actual + remaining, 2)
                                       if isinstance(actual, (int, float)) else None),
            "forecast_remaining": remaining,
            "forecast_tomorrow": daily[1]["kwh"],
            "forecast_seven_days": round(sum(x["kwh"] for x in daily), 2),
            "forecast_next_hour": round(next_hour.get("kwh", 0), 2)
                if next_hour else None,
            "forecast_learning": (
                f"Calibrating ({self.learned_hours} clear-sky hours)"
                if self.learned_hours < 24 else
                f"Learning active ({self.learned_hours} clear-sky hours)"
            ),
            "forecast_updated": (
                self.fetched_at.astimezone(ZoneInfo(self.tz)).strftime("%d %b %H:%M")
                if self.fetched_at else "Unavailable"
            ),
            "daily": daily,
            "hourly": hourly_list,
            "hourly_factors": dict(self.factors),
            "latitude_source": "Home Assistant home coordinates",
            "forecast_model": "PV-side forecast (not capped at 10 kW AC) + clear-sky corrections",
            "note": "10 kW AC limit does not cap PV-side output during DC battery charging. Low output alone cannot distinguish shading, weather error or curtailment.",
        }

    def on_live_update(self):
        """Called every live poll; integrates output for hourly learning.

        Gap over 45s, incomplete hour, low solar, cloudy hour, and high
        battery SOC all prevent potentially misleading self-calibration.
        """
        now = datetime.now(timezone.utc).timestamp()
        reading = (self.live.data or {})
        power = reading.get("total_pv_power")
        soc = reading.get("battery_soc")
        hour_end = (int(now) // 3600 + 1) * 3600

        if self._hour_end is not None and hour_end != self._hour_end:
            self._finalize_hour(self._hour_end)
            self._hour_kwh = 0.0
            self._hour_coverage = 0.0
            self._hour_soc_peak = 0.0
            self._last_sample_epoch = None
            self._last_power = None
        self._hour_end = hour_end

        if isinstance(soc, (float, int)):
            self._hour_soc_peak = max(self._hour_soc_peak, soc)
        if isinstance(power, (int, float)) and power >= 0:
            if (self._last_sample_epoch is not None and
                    self._last_power is not None):
                dt = now - self._last_sample_epoch
                if 0 < dt <= 45:
                    self._hour_kwh += (power + self._last_power) / 2 * dt / 3600000
                    self._hour_coverage += dt
            self._last_power = power
            self._last_sample_epoch = now
        else:
            self._last_power = None
            self._last_sample_epoch = None

        if self.hours:
            self.async_set_updated_data(self._make_data())

    def _finalize_hour(self, end_epoch):
        forecast = self.hours.get(end_epoch)
        if forecast is None:
            return
        hour_local = datetime.fromtimestamp(end_epoch - 1, timezone.utc).astimezone(
            ZoneInfo(self.tz)
        ).hour
        old = self.factors.get(str(hour_local), 1.0)
        correction = learn_factor(
            old,
            self._hour_kwh,
            forecast.get("base_kwh"),
            forecast.get("cloud"),
            self._hour_coverage,
            self._hour_soc_peak,
        )
        if correction is None:
            return
        self.factors[str(hour_local)] = correction
        self.learned_hours += 1
        # Save only once per eligible hour, not on every 10-second Modbus read.
        self.hass.async_create_task(
            self.store.async_save({
                "factors": self.factors, "learned_hours": self.learned_hours,
            })
        )
