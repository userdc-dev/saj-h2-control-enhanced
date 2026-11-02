"""User-editable, read-only PV forecast for SAJ TOU dashboard.

Only requests weather from Open-Meteo. Never connects to inverter or sends
Modbus writes. Uses its own HA config-entry options, preserving Safe Monitor.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from time import monotonic
import logging
from zoneinfo import ZoneInfo

from aiohttp import ClientTimeout
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers.storage import Store

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
        self.learning_store=Store(hass,1,f"saj_h2_control_forecast_learning_{entry.entry_id}")
        self.factors={}
        self.learned_hours=0
        self._learning_settings_key=None
        self._learning_hour_end=None
        self._sample_at=None
        self._sample_power=None
        self._kwh_actual=0.0
        self._coverage=0.0
        self._peak_soc=0.0

    async def async_load_learning(self):
        try:
            saved=await self.learning_store.async_load() or {}
            values=saved.get("factors",{})
            self.factors={str(k):float(v) for k,v in values.items()
                          if str(k).isdigit() and 0<=int(k)<=23
                          and 0.65<=float(v)<=1.15}
            self.learned_hours=max(0,int(saved.get("learned_hours",0)))
            self._learning_settings_key=saved.get("settings_key")
        except (TypeError,ValueError,KeyError) as exc:
            _LOGGER.warning("Invalid solar learning history; resetting: %s",exc)
            self.factors={}
            self.learned_hours=0

    async def _persist_learning(self):
        await self.learning_store.async_save({
            "factors":self.factors,
            "learned_hours":self.learned_hours,
            "settings_key":self._learning_settings_key,
        })

    def on_live_update(self):
        """Learn only from observed reliable clear-sky hours, never device writes."""
        now=datetime.now(timezone.utc).timestamp()
        sample=self._learning_source()
        power=sample.get("total_pv_power")
        soc=sample.get("battery_soc")
        end=(int(now)//3600+1)*3600
        if self._learning_hour_end is not None and end!=self._learning_hour_end:
            self._finalize_learning(self._learning_hour_end)
            self._kwh_actual=0.0
            self._coverage=0.0
            self._peak_soc=0.0
            self._sample_at=None
            self._sample_power=None
        self._learning_hour_end=end
        if isinstance(soc,(int,float)) and 0<=soc<=100:
            self._peak_soc=max(self._peak_soc,float(soc))
        if isinstance(power,(int,float)) and 0<=power<=90000:
            if self._sample_at is not None and self._sample_power is not None:
                dt=now-self._sample_at
                if 0<dt<=45:
                    self._kwh_actual+=(float(power)+self._sample_power)*dt/7200000
                    self._coverage+=dt
            self._sample_at=now
            self._sample_power=float(power)
        else:
            self._sample_at=None
            self._sample_power=None

    def _learning_source(self):
        monitor=getattr(self,"_live_monitor",None)
        return (monitor.data or {}) if monitor is not None else {}

    def _finalize_learning(self,end_epoch):
        reference=self._forecast_hours.get(end_epoch)
        if reference is None or self._coverage<2700 or self._peak_soc>=97:
            return
        expected=reference.get("base_kwh",0)
        cloud=reference.get("cloud",100)
        if expected<0.7 or cloud is None or cloud>25:
            return
        if self._kwh_actual<0:
            return
        local_hour=datetime.fromtimestamp(end_epoch-1,timezone.utc).astimezone(
            ZoneInfo(self.hass.config.time_zone or "Australia/Adelaide")).hour
        key=str(local_hour)
        observed=max(0.65,min(1.15,self._kwh_actual/expected))
        previous=self.factors.get(key,1.0)
        self.factors[key]=round(max(.65,min(1.15,previous*.85+observed*.15)),4)
        self.learned_hours+=1
        # Store only at eligible hour transitions, not on every 10s poll.
        self.hass.async_create_task(self._persist_learning())
        _LOGGER.debug("Solar forecast learned hour %s, ratio %.3f",key,observed)

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
        if self._learning_settings_key != str(settings_key):
            self.factors={}
            self.learned_hours=0
            self._learning_settings_key=str(settings_key)
            self._learning_hour_end=None
            self._sample_at=None
            self._sample_power=None
            self._kwh_actual=0.0
            self._coverage=0.0
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
                    raw=wh * efficiency / 100 / 1000
                    local_hour=datetime.fromtimestamp(end-1,timezone.utc).astimezone(
                        ZoneInfo(self.hass.config.time_zone or "Australia/Adelaide")).hour
                    factor=self.factors.get(str(local_hour),1.0)
                    hours[end] = {
                        "base_kwh":round(raw,4),
                        "kwh":round(raw*factor,4),
                        "cloud":round(sum(cloud_values) / len(cloud_values))
                    }
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
            "learning":{
                "clear_sky_hours":self.learned_hours,
                "hourly_factors":dict(self.factors),
                "status":("Calibrating" if self.learned_hours<24 else "Learning active"),
                "limitation":"Only clear hours with >=45 min reliable observations and SOC below 97% qualify; learning factors bounded 0.65–1.15.",
            },
            "model": "Open-Meteo tilted irradiance; PV-side estimate; no AC clipping",
            "note": ("AC limit is displayed for system reference, not applied as a "
                     "PV production cap because DC battery charging can coexist with AC output."),
        }


