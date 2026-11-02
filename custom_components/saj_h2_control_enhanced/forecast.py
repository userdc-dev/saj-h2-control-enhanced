"""User-editable, read-only PV forecast for SAJ TOU dashboard.

Only requests weather from Open-Meteo. Never connects to inverter or sends
Modbus writes. Uses its own HA config-entry options, preserving Safe Monitor.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from time import monotonic
import logging
import math
from zoneinfo import ZoneInfo

from aiohttp import ClientTimeout
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers.storage import Store

from .forecast_calibration import (
    eligible_samples, score_history, evaluate_issued_forecasts,
    stats_by_hour, factor_for, season, finite,
)

_LOGGER = logging.getLogger(__name__)
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
HISTORY_LOOKBACK_DAYS = 180
HISTORY_AUTO_RECHECK_DAYS = 7
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
        self.seasonal_factors={}
        self.history_calibration={"status":"Not analysed","approved":False,
                                  "eligible_hours":0}
        self.history_last_run=None
        self.history_busy=False
        self.history_error=None
        self.history_source=None
        self.issued_predictions=[]
        self.issued_scores={"days_scored":0,"status":"Awaiting forecasts"}
        self._history_task=None

    async def async_load_learning(self):
        try:
            saved=await self.learning_store.async_load() or {}
            values=saved.get("factors",{})
            self.factors={str(k):float(v) for k,v in values.items()
                          if str(k).isdigit() and 0<=int(k)<=23
                          and 0.65<=float(v)<=1.15}
            self.learned_hours=max(0,int(saved.get("learned_hours",0)))
            self._learning_settings_key=saved.get("settings_key")
            self.seasonal_factors={
                str(k):float(v) for k,v in (saved.get("seasonal_factors") or {}).items()
                if finite(v) and 0.65<=float(v)<=1.15}
            self.history_calibration=saved.get("history_calibration") or self.history_calibration
            self.history_last_run=saved.get("history_last_run")
            self.issued_predictions=(saved.get("issued_predictions") or [])[-90:]
            self.issued_scores=saved.get("issued_scores") or self.issued_scores
        except (TypeError,ValueError,KeyError) as exc:
            _LOGGER.warning("Invalid solar learning history; resetting: %s",exc)
            self.factors={}
            self.learned_hours=0

    async def _persist_learning(self):
        await self.learning_store.async_save({
            "factors":self.factors,
            "learned_hours":self.learned_hours,
            "settings_key":self._learning_settings_key,
            "seasonal_factors":self.seasonal_factors,
            "history_calibration":self.history_calibration,
            "history_last_run":self.history_last_run,
            "issued_predictions":self.issued_predictions[-90:],
            "issued_scores":self.issued_scores,
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

    def _hour_factor(self, start_epoch):
        """Apply validated seasonal history, blended with cautious live learning.

        Never compound two independent correction factors multiplicatively.
        An unvalidated historical backtest cannot alter a forecast.
        """
        local=datetime.fromtimestamp(start_epoch,timezone.utc).astimezone(
            ZoneInfo(self.hass.config.time_zone or "Australia/Adelaide"))
        hour=str(local.hour)
        live=self.factors.get(hour,1.0)
        if not self.history_calibration.get("approved"):
            return live
        local_season=season(local.month,self.hass.config.latitude)
        historical=factor_for(self.seasonal_factors,local_season,local.hour)
        if historical==1.0:
            return live
        has_live=hour in self.factors
        factor=0.8*historical+0.2*live if has_live else historical
        return max(0.65,min(1.15,factor))

    def _save_issued_forecast(self,settings):
        """Capture next-day forecast *before* the date occurs.

        Do not synthesize old forecasts from current/archive weather.
        This is called only when a fresh weather response was fetched.
        """
        now=datetime.now(timezone.utc)
        tz=ZoneInfo(self.hass.config.time_zone or "Australia/Adelaide")
        today=now.astimezone(tz).date()
        tomorrow=today+timedelta(days=1)
        daytime=0.0
        full_day=0.0
        for end,item in self._forecast_hours.items():
            local=datetime.fromtimestamp(end-3600,timezone.utc).astimezone(tz)
            if local.date()!=tomorrow:
                continue
            predicted=item["base_kwh"]*self._hour_factor(end-3600)
            full_day+=predicted
            if 7<=local.hour<=18:
                daytime+=predicted
        if daytime<0.1:
            return
        target=tomorrow.isoformat()
        if any(row.get("target_date")==target for row in self.issued_predictions):
            return
        self.issued_predictions.append({
            "target_date":target,"issued_at":now.isoformat(),
            "predicted_kwh":round(full_day,3),
            "predicted_daytime_kwh":round(daytime,3),
            "model_type":"weather_forecast_issued_before_day",
            "settings_key":self._learning_settings_key,
        })
        self.issued_predictions=self.issued_predictions[-90:]
        self.hass.async_create_task(self._persist_learning())

    def _history_entity_ids(self):
        """Select already-registered HA Recorder statistic entities.

        Prefer the ORIGINAL Safe Monitor measurements, which may have much
        longer history than recently introduced human-readable aliases.
        """
        pv=["sensor.saj_h2_safe_monitor_total_solar_power"]
        soc=["sensor.saj_h2_safe_monitor_battery_state_of_charge"]
        for state in self.hass.states.async_all():
            attrs=state.attributes
            name=state.entity_id
            role=attrs.get("saj_energy_role")
            if role=="solar_production_power" and name not in pv:
                pv.append(name)
            if role=="battery_state_of_charge" and name not in soc:
                soc.append(name)
            if attrs.get("device_class")=="power" and (
                "saj_h2_safe_monitor" in name and "solar" in name and
                name not in pv):
                pv.append(name)
            if attrs.get("device_class")=="battery" and (
                "saj_h2_safe_monitor" in name and
                name not in soc):
                soc.append(name)
        return pv[:8],soc[:8]

    async def _recorder_stats(self,days):
        """HA built-in long-term statistics, not a raw SQLite / custom DB."""
        from homeassistant.components.recorder.statistics import statistics_during_period
        now=datetime.now(timezone.utc)
        start=now-timedelta(days=days)
        pv,soc=self._history_entity_ids()
        ids=set(pv+soc)
        result=await self.hass.async_add_executor_job(
            statistics_during_period,self.hass,start,now,ids,
            "hour",{"power":"W"},{"mean","max"})
        if not isinstance(result,dict):
            return [],[],"Recorder returned no statistics"
        pv_id=next((name for name in pv if len(result.get(name,[]))>=8),None)
        soc_id=next((name for name in soc if len(result.get(name,[]))>=8),None)
        return (result.get(pv_id,[]) if pv_id else [],
                result.get(soc_id,[]) if soc_id else [],
                pv_id or "No solar power long-term statistics")

    async def _archive_weather(self,start_day,end_day,groups):
        """Request reanalysis irradiance by physical panel grouping."""
        session=async_get_clientsession(self.hass)
        async def group_archive(group):
            azimuth=((group["azimuth"]-180+180)%360)-180
            params={
                "latitude":self.hass.config.latitude,
                "longitude":self.hass.config.longitude,
                "start_date":start_day,"end_date":end_day,
                "hourly":"global_tilted_irradiance,cloud_cover",
                "tilt":group["tilt"],"azimuth":azimuth,
                "timezone":"UTC","timeformat":"unixtime",
            }
            async with session.get(ARCHIVE_URL,params=params,
                                   timeout=ClientTimeout(total=60)) as response:
                response.raise_for_status()
                body=await response.json()
            hourly=body.get("hourly") or {}
            stamps=hourly.get("time") or []
            gti=hourly.get("global_tilted_irradiance") or []
            clouds=hourly.get("cloud_cover") or []
            if not len(stamps)==len(gti)==len(clouds):
                raise ValueError("Archive hourly weather values are incomplete")
            # Open-Meteo radiation is a PRECEDING-hour average at its
            # timestamp. HA hourly mean power is keyed by the START of that
            # physical hour. Shift archive timestamps back one hour, matching
            # the existing live forecast's hourly-end convention.
            return {int(ts)-3600:(value,cloud) for ts,value,cloud in
                    zip(stamps,gti,clouds)}
        return await asyncio.gather(*(group_archive(group) for group in groups))

    async def async_backfill_history(self,days=HISTORY_LOOKBACK_DAYS,force=False):
        """Optional monthly/seasonal calibration with true holdout scoring.

        Run independently of the Modbus control coordinator. Never write the
        inverter, and never substitute a current forecast for historic weather.
        """
        if self.history_busy:
            return {"status":"Already scanning history","busy":True}
        if days not in (30,90,180,365):
            raise ValueError("Historical lookback must be 30, 90, 180 or 365 days")
        if not force and self.history_last_run:
            try:
                last=datetime.fromisoformat(self.history_last_run)
                if datetime.now(timezone.utc)-last<timedelta(days=HISTORY_AUTO_RECHECK_DAYS):
                    return {"status":"Recently scanned","busy":False}
            except ValueError:
                pass
        self.history_busy=True
        self.history_error=None
        self.history_calibration["status"]="Checking Home Assistant long-term statistics"
        self._publish_learning()
        try:
            settings=settings_for(self.entry)
            groups,efficiency,limit=validate_settings(
                settings["groups"],settings["efficiency"],settings["ac_limit_kw"])
            stat_power,stat_soc,source=await self._recorder_stats(days)
            self.history_source=source
            tz=ZoneInfo(self.hass.config.time_zone or "Australia/Adelaide")
            self.issued_scores=evaluate_issued_forecasts(
                self.issued_predictions,stat_power,tz)
            if len(stat_power)<28 or len(stat_soc)<28:
                self.seasonal_factors={}
                self.history_calibration={
                    "status":"Waiting for more long-term statistics",
                    "approved":False,"power_stat_hours":len(stat_power),
                    "soc_stat_hours":len(stat_soc),
                    "eligible_hours":0,
                    "notes":"At least 28 hourly solar and SOC statistics are needed; older data cannot be invented.",
                }
            else:
                from .forecast_calibration import timestamp
                starts=[timestamp(row) for row in stat_power]
                starts=[t for t in starts if t is not None]
                if not starts:
                    raise ValueError("Solar statistics have no usable timestamps")
                earliest=datetime.fromtimestamp(min(starts),timezone.utc)
                now=datetime.now(timezone.utc)
                # Archive weather is allowed to lag behind live forecast data.
                end_day=(now-timedelta(days=1)).date()
                start_day=(earliest-timedelta(days=1)).date()
                if start_day>end_day:
                    raise ValueError("No completed historical weather days available")
                archives=await self._archive_weather(
                    start_day.isoformat(),end_day.isoformat(),groups)
                samples,quality=eligible_samples(
                    stat_power,stat_soc,groups,efficiency,
                    archives,tz,self.hass.config.latitude)
                assessed=score_history(samples,quality)
                self.history_calibration={
                    k:v for k,v in assessed.items() if k!="factors"}
                self.history_calibration["lookback_days"]=days
                self.seasonal_factors=assessed["factors"] if assessed["approved"] else {}
            self.history_last_run=datetime.now(timezone.utc).isoformat()
            await self._persist_learning()
            self._reapply_forecast_factors()
            return {"status":self.history_calibration["status"],
                    "eligible_hours":self.history_calibration.get("eligible_hours",0),
                    "approved":self.history_calibration.get("approved",False),
                    "issued_forecasts_scored":self.issued_scores.get("days_scored",0)}
        except Exception as exc:
            self.history_error=str(exc)[:240]
            self.history_calibration["status"]="History scan unavailable"
            _LOGGER.warning("PV historical learning scan failed: %s",exc)
            return {"status":"History scan unavailable","error":self.history_error}
        finally:
            self.history_busy=False
            self._publish_learning()

    def _reapply_forecast_factors(self):
        """Retain weather observations, but update all corrected kWh."""
        for epoch,item in self._forecast_hours.items():
            item["kwh"]=round(item["base_kwh"]*
                              self._hour_factor(epoch-3600),4)
        self._publish_learning()

    def _publish_learning(self):
        if self.data:
            self.async_set_updated_data(self._make_snapshot(settings_for(self.entry)))

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
            self.seasonal_factors={}
            self.history_calibration={
                "status":"Panel layout changed; historical model needs recalibration",
                "approved":False,"eligible_hours":0}
            self.history_last_run=None
            # Old live forecast skill is not comparable after changing array.
            self.issued_predictions=[]
            self.issued_scores={"days_scored":0,"status":"Awaiting future forecasts"}
            await self._persist_learning()
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
                    factor=self._hour_factor(end-3600)
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
            self._save_issued_forecast(settings)
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
                "limitation":"Clear hours and SOC curtailment guard; factors bounded 0.65–1.15. Historical reanalysis is not an archived forecast.",
                "historical":self.history_calibration,
                "historical_source":self.history_source,
                "historical_last_scan":self.history_last_run,
                "historical_scanning":self.history_busy,
                "historical_error":self.history_error,
                "seasonal_factors":dict(self.seasonal_factors),
                "issued_forecast_accuracy":self.issued_scores,
            },
            "model": "Open-Meteo tilted irradiance; PV-side estimate; no AC clipping",
            "note": ("AC limit is displayed for system reference, not applied as a "
                     "PV production cap because DC battery charging can coexist with AC output."),
        }


