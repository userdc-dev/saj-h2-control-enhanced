"""Read-only energy accounting and signed-tariff estimates for SAJ.

Never performs Modbus writes. Integrates existing Safe Monitor power readings
conservatively with trapezoidal zero-crossing handling, and persists totals.
These are estimates, NOT utility settlement meter readings. Gaps > 60s are
excluded and periods before first installation are not retroactively invented.
"""
from __future__ import annotations

from datetime import datetime, timezone
from time import monotonic
import logging

from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)
DEFAULT_PRICING = {
    "import_rate": 0.35,   # AUD/customer cost per kWh; negative => paid to import
    "export_rate": 0.05,   # AUD/export income per kWh; negative => fee to export
    "daily_supply": 1.00, # AUD/day customer cost; signed allowed
    "currency": "AUD",
    "configured": False,
}
MAX_GAP_SECONDS = 60


def validate_pricing(import_rate, export_rate, daily_supply):
    values = []
    for key, value in (
        ("Import rate", import_rate), ("Export rate", export_rate),
        ("Daily supply", daily_supply)
    ):
        try:
            number = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{key} must be a number") from exc
        if not -100 <= number <= 100:
            raise ValueError(f"{key} is outside the permitted signed range -100 to 100 AUD")
        values.append(round(number, 6))
    return tuple(values)


def pricing_for(entry):
    result = dict(DEFAULT_PRICING)
    result.update({k: v for k, v in entry.options.items() if k in DEFAULT_PRICING})
    return result


def split_grid_energy(start_w, end_w, seconds):
    """Return import/export kWh for linear signed W. No mixed-sign bias."""
    if seconds <= 0 or seconds > MAX_GAP_SECONDS:
        return 0.0, 0.0
    a, b = float(start_w), float(end_w)
    if a * b >= 0:
        area_wh = (a+b)*seconds/7200
        return max(0, area_wh)/1000, max(0, -area_wh)/1000
    # Linear crossing: divide interval at zero rather than canceling flows.
    portion = abs(a)/(abs(a)+abs(b))
    first = a * seconds * portion / 2 / 3600000
    second = b * seconds * (1-portion) / 2 / 3600000
    return max(0, first)+max(0, second), max(0, -first)+max(0, -second)


def estimate_cost(import_kwh, export_kwh, import_rate, export_rate,
                  supply_charge=0):
    """Positive result is customer expense; negative is net credit."""
    if import_kwh is None or export_kwh is None:
        return None
    return round(import_kwh*import_rate - export_kwh*export_rate + supply_charge, 2)


def estimate_benefit(home_kwh, import_kwh, export_kwh,
                     import_rate, export_rate):
    """Illustrative net self-supply/export benefit; never battery-only savings."""
    if any(v is None for v in (home_kwh, import_kwh, export_kwh)):
        return None
    # Baseline assumes entire measured home demand was imported at flat rate.
    # Does NOT isolate solar from battery; can be negative under negative rates.
    avoided_home = max(0, home_kwh-import_kwh)
    return round(avoided_home*import_rate + export_kwh*export_rate, 2)


def local_period(now, tz):
    local = now.astimezone(tz)
    return local.date().isoformat(), local.strftime("%Y-%m")


def snapshot_costs(totals, pricing, now, tz):
    """Generate partial-period estimates from known coverage only."""
    day_key, month_key = local_period(now, tz)
    elapsed_today = (
        (now.astimezone(tz) -
         datetime.combine(now.astimezone(tz).date(),
                          datetime.min.time(), tzinfo=tz)).total_seconds()
    )
    # Count elapsed local calendar days including fraction of current day.
    month_start = now.astimezone(tz).replace(day=1,hour=0,minute=0,second=0,microsecond=0)
    elapsed_month_days = (now.astimezone(tz)-month_start).total_seconds()/86400
    day = totals.get("today", {})
    month = totals.get("month", {})
    costs = {}
    for kind, row, supply_fraction in (
        ("today", day, max(0,elapsed_today/86400)),
        ("month", month, max(0,elapsed_month_days)),
    ):
        if not row or row.get("period") not in (day_key if kind=="today" else month_key,):
            costs[kind] = None
            continue
        imp, exp = row.get("import_kwh"), row.get("export_kwh")
        if imp is None or exp is None:
            costs[kind] = None
            continue
        supply_fraction = max(0, row.get("coverage_seconds", 0)/86400)
        home = row.get("home_kwh") if (
            row.get("coverage_seconds",0)>0 and
            row.get("home_coverage_seconds",0)>=0.8*row["coverage_seconds"]
        ) else None
        battery = row.get("battery_discharge_kwh") if (
            row.get("coverage_seconds",0)>0 and
            row.get("battery_discharge_coverage_seconds",0)>=0.8*row["coverage_seconds"]
        ) else None
        costs[kind] = {
            "import_kwh": round(imp, 3),
            "export_kwh": round(exp, 3),
            "import_cost": round(imp*pricing["import_rate"],2),
            "export_credit": round(exp*pricing["export_rate"],2),
            "supply_cost": round(supply_fraction*pricing["daily_supply"],2),
            "net_cost": estimate_cost(imp,exp,pricing["import_rate"],
                                      pricing["export_rate"],
                                      supply_fraction*pricing["daily_supply"]),
            "coverage_seconds": round(row.get("coverage_seconds",0)),
            "solar_kwh": round(row["solar_kwh"],3)
                if row.get("solar_kwh") is not None else None,
            "home_kwh": round(home,3) if home is not None else None,
            "battery_discharge_kwh": round(battery,3) if battery is not None else None,
            "self_supply_estimated_benefit": estimate_benefit(
                home,imp,exp,pricing["import_rate"],pricing["export_rate"]),
            "battery_discharge_illustrative_value": (
                round(battery*pricing["import_rate"],2)
                if battery is not None else None),
            "period_partial": True,
            "label": "since tracking began / available monitored intervals",
        }
    return costs


class SajEnergyAccounting(DataUpdateCoordinator):
    """Read-only state aggregator attached to existing Safe Monitor callbacks."""

    def __init__(self, hass, entry, monitor):
        from zoneinfo import ZoneInfo
        super().__init__(hass,_LOGGER,name="SAJ energy accounting (estimates)")
        self.entry=entry
        self.monitor=monitor
        self.tz=ZoneInfo(hass.config.time_zone or "Australia/Adelaide")
        self.store=Store(hass,1,f"saj_h2_control_accounting_{entry.entry_id}")
        self.totals={"lifetime":{"import_kwh":0.0,"export_kwh":0.0},
                     "today":{},"month":{}}
        self.last_time=None
        self.last_grid_power=None
        self.last_home_power=None
        self.last_solar_power=None
        self.last_battery_power=None
        self._last_save=0.0
        self._last_meter=None

    async def async_initialize(self):
        try:
            record=await self.store.async_load() or {}
            for key in ("lifetime","today","month"):
                stored=record.get(key)
                if isinstance(stored,dict):
                    self.totals[key]=stored
        except Exception as exc:
            _LOGGER.warning("Could not load past energy estimates: %s",exc)
        self.refresh_snapshot()

    def refresh_snapshot(self):
        data=self.monitor.data or {}
        pricing=pricing_for(self.entry)
        if not self.entry.options.get("currency"):
            pricing["currency"]=self.hass.config.currency or "AUD"
        self.async_set_updated_data({
            **data,
            "accounting":self.totals,
            "costs":snapshot_costs(
                self.totals,pricing,datetime.now(timezone.utc),self.tz),
            "pricing":pricing,
            "estimated_from_power":True,
            "grid_direction_unverified":True,
        })

    def on_monitor_update(self):
        now=datetime.now(timezone.utc)
        data=self.monitor.data or {}
        grid=data.get("grid_power")
        home=data.get("home_load_power")
        solar=data.get("total_pv_power")
        battery=data.get("battery_power")
        day,month=local_period(now,self.tz)
        daily=self.totals.setdefault("today",{})
        monthly=self.totals.setdefault("month",{})
        if daily.get("period")!=day:
            self.totals["today"]=daily={"period":day,"import_kwh":0.0,
                "export_kwh":0.0,"home_kwh":0.0,"solar_kwh":0.0,
                "battery_discharge_kwh":0.0,"coverage_seconds":0.0,
                "home_coverage_seconds":0.0,
                "solar_coverage_seconds":0.0,
                "battery_discharge_coverage_seconds":0.0}
        if monthly.get("period")!=month:
            self.totals["month"]=monthly={"period":month,"import_kwh":0.0,
                "export_kwh":0.0,"coverage_seconds":0.0}
        if (grid is not None and self.last_grid_power is not None
                and self.last_time is not None):
            dt=(now-self.last_time).total_seconds()
            # Prevent assigning one time interval to two different days/months.
            old_day,old_month=local_period(self.last_time,self.tz)
            if 0<dt<=MAX_GAP_SECONDS and old_day==day and old_month==month:
                imp,exp=split_grid_energy(self.last_grid_power,grid,dt)
                for row in (daily,monthly,self.totals["lifetime"]):
                    row["import_kwh"]=row.get("import_kwh",0)+imp
                    row["export_kwh"]=row.get("export_kwh",0)+exp
                # Approximate self-consumption and battery value only using
                # intervals with simultaneous valid samples, never full-day
                # counters mixed with a partially recorded grid history.
                for field,current,previous in (
                    ("home_kwh",home,self.last_home_power),
                    ("solar_kwh",solar,self.last_solar_power),
                    ("battery_discharge_kwh",battery,self.last_battery_power)
                ):
                    if isinstance(current,(int,float)) and isinstance(previous,(int,float)):
                        energy=max(0,(max(current,0)+max(previous,0))/2)*dt/3600000
                        for row in (daily,monthly):
                            row[field]=row.get(field,0.0)+energy
                            row[field.replace("_kwh","_coverage_seconds")]=(
                                row.get(field.replace("_kwh","_coverage_seconds"),0.0)+dt)
                    # Missing measurements remain uncovered, not invented.
                daily["coverage_seconds"]+=dt
                monthly["coverage_seconds"]+=dt
        if isinstance(grid,(float,int)):
            self.last_grid_power=grid
            self.last_time=now
        else:
            self.last_grid_power=None
            self.last_time=None
        self.last_home_power=home
        self.last_solar_power=solar
        self.last_battery_power=battery
        self.refresh_snapshot()
        if monotonic()-self._last_save>=60:
            self._last_save=monotonic()
            self.hass.async_create_task(self.async_save())

    async def async_save(self):
        await self.store.async_save(self.totals)
