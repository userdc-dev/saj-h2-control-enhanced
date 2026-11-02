"""Read-only, gap-aware HA energy accounting and time-of-use cost estimates.

Power samples are from the existing Safe Monitor; no inverter Modbus writes.
Existing cumulative kWh estimates are preserved for Home Assistant Energy.
Tariff money is accrued at the *time of each valid measured interval*, never
by re-pricing the whole current day at whichever tariff is selected now.
"""
from __future__ import annotations

from datetime import datetime, timezone
from time import monotonic
import logging
import math

from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .tariffs import (
    EXAMPLE_PROFILE, price_power_interval, choose_rates, full_daily_supply,
)

_LOGGER = logging.getLogger(__name__)
DEFAULT_PRICING={
    "import_rate":0.35,
    "export_rate":0.05,
    "daily_supply":1.0,
    "currency":"AUD",
    "configured":False,
}
MAX_GAP_SECONDS=60


def validate_pricing(import_rate, export_rate, daily_supply):
    """Legacy flat-tariff API; kept for backward compatibility."""
    results=[]
    for name,value in (("Import rate",import_rate),
                       ("Export rate",export_rate),
                       ("Daily supply",daily_supply)):
        try:
            n=float(value)
        except (TypeError,ValueError) as exc:
            raise ValueError(f"{name} must be a number") from exc
        if not math.isfinite(n) or not -100<=n<=100:
            raise ValueError(f"{name} is outside the signed range -100 to 100")
        results.append(round(n,6))
    return tuple(results)


def pricing_for(entry):
    result=dict(DEFAULT_PRICING)
    result.update({key:value for key,value in entry.options.items()
                   if key in DEFAULT_PRICING})
    # An old HA config entry may retain earlier signed flat rates. New pricing
    # is opt-in, and *does not* rewrite the legacy settings.
    if isinstance(entry.options.get("tariff_profile"),dict):
        result["tariff_profile"]=entry.options["tariff_profile"]
        result["tariff_revision"]=entry.options.get("tariff_revision")
        result["configured"]=bool(entry.options["tariff_profile"].get("configured"))
    return result


def split_grid_energy(start_w,end_w,seconds):
    """Positive import and positive export kWh for linear signed W interval."""
    if not 0<seconds<=MAX_GAP_SECONDS:
        return 0.0,0.0
    a,b=float(start_w),float(end_w)
    if a*b>=0:
        result=(a+b)*seconds/7200000
        return max(0,result),max(0,-result)
    fraction=abs(a)/(abs(a)+abs(b))
    first=a*seconds*fraction/7200000
    last=b*seconds*(1-fraction)/7200000
    return max(0,first)+max(0,last),max(0,-first)+max(0,-last)


def estimate_cost(import_kwh,export_kwh,import_rate,export_rate,supply_charge=0):
    if import_kwh is None or export_kwh is None:
        return None
    return round(import_kwh*import_rate-export_kwh*export_rate+supply_charge,2)


def estimate_benefit(home_kwh,import_kwh,export_kwh,import_rate,export_rate):
    if any(v is None for v in (home_kwh,import_kwh,export_kwh)):
        return None
    return round(max(0,home_kwh-import_kwh)*import_rate +
                 export_kwh*export_rate,2)


def local_period(now,tz):
    local=now.astimezone(tz)
    return local.date().isoformat(),local.strftime("%Y-%m")


def _money(n):
    return round(n,2) if isinstance(n,(int,float)) and math.isfinite(n) else None


def snapshot_costs(totals,pricing,now,tz):
    """Present accurate priced ledger when available; retain legacy readouts.

    Legacy rows predate the detailed tariff profile, so they are never
    silently treated as high-FiT or peak energy after user changes settings.
    """
    day_key,month_key=local_period(now,tz)
    result={}
    active_profile=(pricing.get("tariff_profile") or {})
    detailed=bool(active_profile.get("configured"))
    for kind,period in (("today",day_key),("month",month_key)):
        row=totals.get(kind) or {}
        if row.get("period")!=period:
            result[kind]=None
            continue
        imp,exp=row.get("import_kwh"),row.get("export_kwh")
        if imp is None or exp is None:
            result[kind]=None
            continue
        seconds=row.get("coverage_seconds",0)
        home=row.get("home_kwh") if (seconds and
            row.get("home_coverage_seconds",0)>=0.8*seconds) else None
        battery=row.get("battery_discharge_kwh") if (seconds and
            row.get("battery_discharge_coverage_seconds",0)>=0.8*seconds) else None
        common={
            "import_kwh":round(imp,3),
            "export_kwh":round(exp,3),
            "solar_kwh":round(row["solar_kwh"],3)
                if row.get("solar_kwh") is not None else None,
            "home_kwh":round(home,3) if home is not None else None,
            "battery_discharge_kwh":round(battery,3)
                if battery is not None else None,
            "coverage_seconds":round(seconds),
            "period_partial":True,
            "label":"Observed intervals only; never a complete utility bill",
        }
        if detailed:
            ledger=row.get("tariff") or {}
            priced_seconds=ledger.get("coverage_seconds",0)
            if priced_seconds<=0 and not ledger.get("supply_charged_dates"):
                result[kind]={
                    **common, "import_cost":None,"export_credit":None,
                    "supply_cost":None,"net_cost":None,"tax_adjustment":None,
                    "self_supply_estimated_benefit":None,
                    "battery_discharge_illustrative_value":None,
                    "tariff_coverage_seconds":0,
                    "high_fit_unverified_difference":None,
                    "import_bands":[],"export_bands":[],
                    "tariff_partial":True,
                    "label":"Tariff tracking starts only after rates saved.",
                }
                continue
            cost=_money(ledger.get("net_cost",0.0))
            result[kind]={
                **common,
                "import_cost":_money(ledger.get("import_cost",0.0)),
                "export_credit":_money(ledger.get("export_credit",0.0)),
                "supply_cost":_money(ledger.get("supply_cost",0.0)),
                "net_cost":cost,
                "tax_adjustment":_money(ledger.get("tax_adjustment",0.0)),
                "high_fit_unverified_difference":_money(
                    ledger.get("high_fit_unverified_difference",0.0)),
                "self_supply_estimated_benefit":_money(
                    ledger.get("avoided_import_value",0.0)+
                    ledger.get("export_credit",0.0))
                    if ledger.get("home_coverage_seconds",0)>=
                       0.8*priced_seconds else None,
                "battery_discharge_illustrative_value":_money(
                    ledger.get("battery_discharge_illustrative_value",0.0))
                    if ledger.get("battery_coverage_seconds",0)>=
                       0.8*priced_seconds else None,
                "tariff_coverage_seconds":round(priced_seconds),
                "supply_days_charged":len(ledger.get("supply_charged_dates") or {}),
                "tariff_partial":True,
                "import_bands":[
                    {"label":key,**{k:round(v,4) for k,v in amount.items()}}
                    for key,amount in sorted(
                        (ledger.get("import_bands") or {}).items())],
                "export_bands":[
                    {"label":key,**{k:round(v,4) for k,v in amount.items()}}
                    for key,amount in sorted(
                        (ledger.get("export_bands") or {}).items())],
                "label":"Time-of-use charges accrued only during observed intervals after tariff activation; earlier readings unpriced.",
            }
        else:
            # Existing v0.5.15 installation has only flat rates. Preserve
            # legacy calculations until the new profile is configured.
            supply=row.get("legacy_supply_cost",0.0) if pricing.get("configured") else 0.0
            result[kind]={
                **common,
                "import_cost":_money(imp*pricing["import_rate"]),
                "export_credit":_money(exp*pricing["export_rate"]),
                "supply_cost":_money(supply),
                "net_cost":estimate_cost(
                    imp,exp,pricing["import_rate"],pricing["export_rate"],supply),
                "self_supply_estimated_benefit":estimate_benefit(
                    home,imp,exp,pricing["import_rate"],pricing["export_rate"]),
                "battery_discharge_illustrative_value":(
                    _money(battery*pricing["import_rate"])
                    if battery is not None else None),
                "tariff_coverage_seconds":0,
                "label":"Legacy flat-rate calculation; replace with verified time-of-use rules.",
            }
    return result


def _new_period(period):
    return {
        "period":period,
        "import_kwh":0.0,"export_kwh":0.0,
        "home_kwh":0.0,"solar_kwh":0.0,
        "battery_discharge_kwh":0.0,
        "coverage_seconds":0.0,
        "home_coverage_seconds":0.0,
        "solar_coverage_seconds":0.0,
        "battery_discharge_coverage_seconds":0.0,
    }


def _new_tariff_ledger():
    return {
        "coverage_seconds":0.0,
        "import_kwh":0.0,"export_kwh":0.0,
        "import_cost":0.0,"export_credit":0.0,"supply_cost":0.0,
        "tax_adjustment":0.0,"net_cost":0.0,
        "high_fit_unverified_difference":0.0,
        "avoided_import_value":0.0,
        "battery_discharge_illustrative_value":0.0,
        "home_coverage_seconds":0.0,"battery_coverage_seconds":0.0,
        "import_bands":{},"export_bands":{},
        "supply_charged_dates":{},
        "supply_tax_adjustment":0.0,
    }


def _interp(start,end,fraction):
    if not isinstance(start,(int,float)) or not isinstance(end,(int,float)):
        return None
    if not math.isfinite(start) or not math.isfinite(end):
        return None
    return start+(end-start)*fraction


class SajEnergyAccounting(DataUpdateCoordinator):
    """Accumulate read-only energy and time-of-use expenses across restarts."""

    def __init__(self,hass,entry,monitor):
        from zoneinfo import ZoneInfo
        super().__init__(hass,_LOGGER,name="SAJ energy accounting (estimates)")
        self.entry=entry
        self.monitor=monitor
        self.tz=ZoneInfo(hass.config.time_zone or "Australia/Adelaide")
        self.store=Store(hass,1,f"saj_h2_control_accounting_{entry.entry_id}")
        self.totals={
            "lifetime":{"import_kwh":0.0,"export_kwh":0.0},
            "today":{},"month":{},
        }
        self.last_time=None
        self.last_grid_power=None
        self.last_home_power=None
        self.last_solar_power=None
        self.last_battery_power=None
        self._last_save=0.0
        self._last_revision=None

    async def async_initialize(self):
        try:
            record=await self.store.async_load() or {}
            for key in ("lifetime","today","month"):
                stored=record.get(key)
                if isinstance(stored,dict):
                    self.totals[key]=stored
        except Exception as exc:
            _LOGGER.warning("Could not load energy accounting storage: %s",exc)
        self._last_revision=self.entry.options.get("tariff_revision")
        # A fixed DAILY supply charge must appear even before any grid-power
        # reading arrives; it is independent of telemetry coverage.
        if self._ensure_daily_supply(datetime.now(timezone.utc)):
            await self.async_save()
        self.refresh_snapshot()

    def refresh_snapshot(self):
        data=self.monitor.data or {}
        pricing=pricing_for(self.entry)
        if not self.entry.options.get("currency"):
            pricing["currency"]=self.hass.config.currency or "AUD"
        moment=datetime.now(timezone.utc)
        profile=pricing.get("tariff_profile") or {}
        active=None
        if profile.get("configured"):
            import_band,export_band=choose_rates(profile,moment.astimezone(self.tz))
            active={"import":import_band,"export":export_band,
                    "checked_at":moment.isoformat()}
        self.async_set_updated_data({
            **data,
            "accounting":self.totals,
            "costs":snapshot_costs(self.totals,pricing,moment,self.tz),
            "current_tariff":active,
            "pricing":pricing,
            "estimated_from_power":True,
            "grid_direction_unverified":True,
        })

    def on_tariff_changed(self):
        """Prevent the last sample from bridging old and new prices."""
        self._last_revision=self.entry.options.get("tariff_revision")
        self.last_time=None
        self.last_grid_power=None
        self.last_home_power=None
        self.last_solar_power=None
        self.last_battery_power=None
        self._ensure_daily_supply(datetime.now(timezone.utc))
        self.refresh_snapshot()

    def _periods(self,local):
        day,month=local_period(local,self.tz)
        for key,period in (("today",day),("month",month)):
            if self.totals.get(key,{}).get("period")!=period:
                self.totals[key]=_new_period(period)
        return self.totals["today"],self.totals["month"]

    def _ensure_daily_supply(self,when):
        """Post a full signed fixed supply charge once per local date.

        The monthly ledger preserves older days, even after rate edits.
        If upgrading from v0.5.16, reconcile the CURRENT day's already
        prorated supply fee instead of adding a second full-day charge.
        Older dates are never silently repriced.
        """
        p=pricing_for(self.entry)
        profile=p.get("tariff_profile") or {}
        local=when.astimezone(self.tz)
        if not profile.get("configured"):
            # Old flat-rate entries still deserve the *whole* daily fixed
            # charge, even without meter readings. Keep this legacy charge
            # separately to avoid changing or duplicating TOU ledgers.
            if not p.get("configured"):
                return False
            day,month=self._periods(local)
            key=local.date().isoformat()
            charged=month.setdefault("legacy_supply_charged_dates",{})
            if key in charged:
                day.setdefault("legacy_supply_cost",charged[key])
                return False
            amount=float(p["daily_supply"])
            charged[key]=amount
            day.setdefault("legacy_supply_charged_dates",{})[key]=amount
            for row in (day,month):
                row["legacy_supply_cost"]=row.get("legacy_supply_cost",0.0)+amount
            return True
        day_key=local.date().isoformat()
        day,month=self._periods(local)
        month_ledger=month.setdefault("tariff",_new_tariff_ledger())
        charged=month_ledger.setdefault("supply_charged_dates",{})
        if day_key in charged:
            # After a previous restart/day rollover, keep today's row in sync
            # if the monthly ledger already contains this date.
            today_ledger=day.setdefault("tariff",_new_tariff_ledger())
            day_charged=today_ledger.setdefault("supply_charged_dates",{})
            if day_key not in day_charged:
                recorded=charged[day_key]
                value=recorded["amount"] if isinstance(recorded,dict) else recorded
                tax=recorded.get("tax",0) if isinstance(recorded,dict) else 0
                today_ledger["supply_cost"]+=value
                today_ledger["net_cost"]+=value
                today_ledger["tax_adjustment"]+=tax
                today_ledger["supply_tax_adjustment"]=tax
                day_charged[day_key]=recorded
            return False
        day_ledger=day.setdefault("tariff",_new_tariff_ledger())
        day_charged=day_ledger.setdefault("supply_charged_dates",{})
        full_amount,full_tax=full_daily_supply(profile)
        # Version migration: yesterday's supply is left intact. TODAY's old
        # pro-rated amount is topped up rather than counted twice.
        previous_amount=day_ledger.get("supply_cost",0.0)
        previous_tax=day_ledger.get("supply_tax_adjustment",0.0)
        if not previous_tax and previous_amount:
            # v0.5.16 had no supply-specific tax field; derive the tax share
            # using the current matching signed tax components.
            base=profile["daily_supply"]
            if abs(base)>1e-12:
                previous_tax=previous_amount*(full_tax/(base+full_tax)) if abs(base+full_tax)>1e-12 else 0.0
        delta=full_amount-previous_amount
        tax_delta=full_tax-previous_tax
        for ledger in (day_ledger,month_ledger):
            ledger["supply_cost"]+=delta
            ledger["net_cost"]+=delta
            ledger["tax_adjustment"]+=tax_delta
            ledger["supply_tax_adjustment"]=ledger.get("supply_tax_adjustment",0.0)+tax_delta
        record={"amount":full_amount,"tax":full_tax,"revision":self.entry.options.get("tariff_revision")}
        day_charged[day_key]=record
        charged[day_key]=record
        return True

    def _tariff_apply(self,day,month,part,profile,previous_home,
                      current_home,previous_battery,current_battery,
                      start,end):
        length=(end-start).total_seconds()
        a=(part["start"]-start).total_seconds()/length
        b=(part["end"]-start).total_seconds()/length
        h0,h1=_interp(previous_home,current_home,a),_interp(
            previous_home,current_home,b)
        ba0,ba1=_interp(previous_battery,current_battery,a),_interp(
            previous_battery,current_battery,b)
        for row in (day,month):
            ledger=row.setdefault("tariff",_new_tariff_ledger())
            dt=part["seconds"]
            ledger["coverage_seconds"]+=dt
            for key in ("import_kwh","export_kwh","import_cost","export_credit",
                        "supply_cost","tax_adjustment","net_cost",
                        "high_fit_unverified_difference"):
                ledger[key]+=part[key]
            for category,band,key_amount,key_cost in (
                ("import_bands",part["import_band"],"import_kwh","import_cost"),
                ("export_bands",part["export_band"],"export_kwh","export_credit")
            ):
                # Keep different historical rates distinct across edits.
                label=f"{band['name']} ({band['rate']:+.4f}/kWh)"
                record=ledger[category].setdefault(label,{"kwh":0.0,"amount":0.0})
                record["kwh"]+=part[key_amount]
                record["amount"]+=part[key_cost]
            if h0 is not None and h1 is not None:
                # Baseline illustrative home kWh not bought from grid, valued
                # at the import band active for that instant.
                home=max(0,(h0+h1)/2)*dt/3600000
                avoided=max(0,home-part["import_kwh"])
                ledger["avoided_import_value"]+=(
                    avoided*part["import_band"]["rate"])
                ledger["home_coverage_seconds"]+=dt
            if ba0 is not None and ba1 is not None:
                discharge=split_grid_energy(ba0,ba1,dt)[0]
                ledger["battery_discharge_illustrative_value"]+=(
                    discharge*part["import_band"]["rate"])
                ledger["battery_coverage_seconds"]+=dt

    def on_monitor_update(self):
        now=datetime.now(timezone.utc)
        data=self.monitor.data or {}
        grid=data.get("grid_power")
        home=data.get("home_load_power")
        solar=data.get("total_pv_power")
        battery=data.get("battery_power")
        revision=self.entry.options.get("tariff_revision")
        if revision!=self._last_revision:
            self.on_tariff_changed()
        previous=self.last_time
        if (isinstance(grid,(int,float)) and math.isfinite(grid)
                and previous is not None and
                isinstance(self.last_grid_power,(int,float))):
            dt=(now-previous).total_seconds()
            if 0<dt<=MAX_GAP_SECONDS:
                options=pricing_for(self.entry)
                profile=options.get("tariff_profile") or EXAMPLE_PROFILE
                # Minute-by-minute split ensures tariff switching, local
                # midnight and summer/winter DST changes are respected.
                priced=price_power_interval(
                    previous,now,self.last_grid_power,grid,profile,self.tz,
                    split_grid_energy,include_supply=False)
                for part in priced:
                    day,month=self._periods(part["local"])
                    self._ensure_daily_supply(part["local"])
                    imp=part["import_kwh"]
                    exp=part["export_kwh"]
                    for row in (day,month,self.totals["lifetime"]):
                        row["import_kwh"]=row.get("import_kwh",0.0)+imp
                        row["export_kwh"]=row.get("export_kwh",0.0)+exp
                    for row in (day,month):
                        row["coverage_seconds"]+=part["seconds"]
                    full=(now-previous).total_seconds()
                    for key,old,current in (
                        ("home_kwh",self.last_home_power,home),
                        ("solar_kwh",self.last_solar_power,solar),
                        ("battery_discharge_kwh",self.last_battery_power,battery)
                    ):
                        st=_interp(old,current,
                            (part["start"]-previous).total_seconds()/full)
                        en=_interp(old,current,
                            (part["end"]-previous).total_seconds()/full)
                        if st is None or en is None:
                            continue
                        if key=="battery_discharge_kwh":
                            energy=split_grid_energy(st,en,part["seconds"])[0]
                        else:
                            energy=max(0,(max(st,0)+max(en,0))/2) * part["seconds"]/3600000
                        for row in (day,month):
                            row[key]=row.get(key,0.0)+energy
                            cov=key.replace("_kwh","_coverage_seconds")
                            row[cov]=row.get(cov,0.0)+part["seconds"]
                    if profile.get("configured"):
                        self._tariff_apply(day,month,part,profile,
                            self.last_home_power,home,
                            self.last_battery_power,battery,previous,now)
        # Make sure a whole-day fixed supply charge is shown even if every
        # grid power sensor was unavailable for this update.
        self._ensure_daily_supply(now)
        self.last_time=now if isinstance(grid,(int,float)) and math.isfinite(grid) else None
        self.last_grid_power=grid if self.last_time else None
        self.last_home_power=home
        self.last_solar_power=solar
        self.last_battery_power=battery
        self.refresh_snapshot()
        if monotonic()-self._last_save>=60:
            self._last_save=monotonic()
            self.hass.async_create_task(self.async_save())

    async def async_save(self):
        await self.store.async_save(self.totals)
