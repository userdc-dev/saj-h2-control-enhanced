"""Time-of-use electricity tariffs: pure, timezone-aware, read-only maths.

Rules use LOCAL wall-clock weekdays (Mon=0..Sun=6). Windows are half-open;
overnight windows belong to the weekday they start on. Validation rejects
ambiguous overlapping import bands. A default import rate covers every gap.
High FiT NEVER proves energy source; battery-only plans are shown as potential
uplift, not silently assumed earned.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone, timedelta
import math
import re

DAYS=list(range(7))
MAX_RATE=100.0
MAX_BANDS=12
MAX_WINDOWS=24

EXAMPLE_PROFILE={
    "version":1,
    "configured":False,
    "default_import_rate":0.35,
    "import_bands":[
        {"id":"peak","name":"Peak","rate":0.52,
         "windows":[{"start":"07:00","end":"09:00","days":DAYS},
                    {"start":"17:00","end":"21:00","days":DAYS}]},
        {"id":"offpeak","name":"Off-peak","rate":0.24,
         "windows":[{"start":"21:00","end":"07:00","days":DAYS}]},
        {"id":"sponge","name":"Solar sponge","rate":0.12,
         "windows":[{"start":"10:00","end":"15:00","days":DAYS}]},
    ],
    "export_standard_rate":0.05,
    "export_standard_windows":[],
    "export_fallback_rate":0.05,
    "export_high_rate":0.25,
    "export_high_windows":[{"start":"17:00","end":"21:00","days":DAYS}],
    # When battery-only eligibility cannot be metered reliably, DO NOT apply
    # the higher payment to the bill: show a potential difference separately.
    "high_fit_eligibility":"battery_only_unverified",
    "daily_supply":1.00,
    "gst_percent":10.0,
    "gst_mode":"included",
    "gst_on_import":True,
    "gst_on_export":False,
    "gst_on_supply":True,
    "other_tax_percent":0.0,
    "other_tax_on_import":True,
    "other_tax_on_export":False,
    "other_tax_on_supply":True,
    "currency":"AUD",
}
_TIME_RE=re.compile(r"^(?:[01][0-9]|2[0-3]):[0-5][0-9]$")


def _number(value,label,low=-MAX_RATE,high=MAX_RATE):
    if isinstance(value,bool):
        raise ValueError(f"{label} must be a number, not a checkbox")
    try:
        n=float(value)
    except (ValueError,TypeError) as exc:
        raise ValueError(f"{label} must be a number") from exc
    if not math.isfinite(n) or not low<=n<=high:
        raise ValueError(f"{label} must be between {low:g} and {high:g}")
    return round(n,6)


def _minutes(value):
    if not isinstance(value,str) or not _TIME_RE.fullmatch(value):
        raise ValueError(f"Use 24-hour HH:MM time, got {value!r}")
    return int(value[:2])*60+int(value[3:])


def _windows(windows,label):
    if not isinstance(windows,list) or len(windows)>MAX_WINDOWS:
        raise ValueError(f"{label}: at most {MAX_WINDOWS} time windows allowed")
    clean=[]
    for i,w in enumerate(windows,1):
        if not isinstance(w,dict):
            raise ValueError(f"{label}, window {i}: invalid row")
        start=w.get("start")
        end=w.get("end")
        sm,em=_minutes(start),_minutes(end)
        if sm==em:
            raise ValueError(f"{label}, window {i}: start and end must differ")
        days=w.get("days")
        if (not isinstance(days,list) or not days
                or any(type(d) is not int or not 0<=d<=6 for d in days)
                or len(set(days))!=len(days)):
            raise ValueError(f"{label}, window {i}: select valid weekdays")
        clean.append({"start":start,"end":end,"days":sorted(days)})
    return clean


def _week_intervals(window):
    """Expand one window across local weekly minutes; handle overnight/week wrap."""
    sm,em=_minutes(window["start"]),_minutes(window["end"])
    for day in window["days"]:
        start=day*1440+sm
        end=day*1440+em+(1440 if sm>em else 0)
        if end<=10080:
            yield start,end
        else:
            yield start,10080
            yield 0,end-10080


def validate_profile(profile):
    if not isinstance(profile,dict):
        raise ValueError("Tariff profile must be an object")
    # Only accept expected fields (avoid storing client-provided secrets/data).
    p=deepcopy(EXAMPLE_PROFILE)
    for key in p:
        if key in profile:
            p[key]=profile[key]
    if p.get("version")!=1:
        raise ValueError("Unsupported tariff profile version")
    for key in ("default_import_rate","export_standard_rate",
                "export_fallback_rate","export_high_rate","daily_supply"):
        p[key]=_number(p[key],key)
    for key in ("gst_percent","other_tax_percent"):
        p[key]=_number(p[key],key,0,100)
    if p["gst_mode"] not in ("included","exclusive"):
        raise ValueError("GST must be included or added on top")
    if p["high_fit_eligibility"] not in ("all_exports","battery_only_unverified"):
        raise ValueError("Select whether high FiT applies to every export")
    for key in ("gst_on_import","gst_on_export","gst_on_supply",
                "other_tax_on_import","other_tax_on_export","other_tax_on_supply"):
        if type(p[key]) is not bool:
            raise ValueError(f"{key} must be enabled or disabled")
    if type(p["configured"]) is not bool:
        raise ValueError("Configured must be true or false")
    if not isinstance(p["currency"],str) or not re.fullmatch(r"[A-Z]{3}",p["currency"]):
        raise ValueError("Currency must be a three-letter ISO code")
    raw=p["import_bands"]
    if not isinstance(raw,list) or len(raw)>MAX_BANDS:
        raise ValueError(f"At most {MAX_BANDS} import rate categories")
    bands=[]; all_intervals=[]; ids=set()
    for i,b in enumerate(raw,1):
        if not isinstance(b,dict):
            raise ValueError(f"Import category {i}: invalid")
        name=str(b.get("name","")).strip()
        if not 1<=len(name)<=45:
            raise ValueError(f"Import category {i} needs a name of 1–45 characters")
        ident=b.get("id")
        if not isinstance(ident,str) or not re.fullmatch(r"[a-zA-Z0-9_-]{1,50}",ident):
            raise ValueError(f"Import category {name}: invalid ID")
        if ident in ids:
            raise ValueError(f"Duplicate category ID {ident}")
        ids.add(ident)
        windows=_windows(b.get("windows",[]),name)
        if not windows:
            raise ValueError(f"Import category {name} needs at least one time window")
        for w in windows:
            for st,en in _week_intervals(w):
                all_intervals.append((st,en,name))
        bands.append({"id":ident,"name":name,
                      "rate":_number(b.get("rate"),f"{name} rate"),
                      "windows":windows})
    all_intervals.sort(key=lambda row:(row[0],row[1]))
    for previous,current in zip(all_intervals,all_intervals[1:]):
        if current[0]<previous[1]:
            raise ValueError(
                f"Import times overlap: {previous[2]} and {current[2]}. "
                "Use non-overlapping bands; fallback rate covers all gaps.")
    p["import_bands"]=bands
    p["export_standard_windows"]=_windows(
        p["export_standard_windows"],"Standard export FiT")
    p["export_high_windows"]=_windows(
        p["export_high_windows"],"High export FiT")
    # Multiple overlapping high FIT windows are redundant but not ambiguous.
    return p


def _matches(window,when):
    minute=when.hour*60+when.minute
    day=when.weekday()
    start,end=_minutes(window["start"]),_minutes(window["end"])
    if start<end:
        return day in window["days"] and start<=minute<end
    if minute>=start:
        return day in window["days"]
    return (day-1)%7 in window["days"] and minute<end


def choose_rates(profile,when):
    """Return import rate band and export rate band for local aware datetime."""
    for b in profile["import_bands"]:
        if any(_matches(w,when) for w in b["windows"]):
            imp={"id":b["id"],"name":b["name"],"rate":b["rate"]}
            break
    else:
        imp={"id":"default","name":"Other / fallback","rate":profile["default_import_rate"]}
    high=any(_matches(w,when) for w in profile["export_high_windows"])
    eligible=high and profile["high_fit_eligibility"]=="all_exports"
    explicit=profile.get("export_standard_windows",[])
    standard=(not explicit or any(_matches(w,when) for w in explicit)
              or (high and not eligible))
    if eligible:
        exp_id,exp_name,exp_rate="high","High FiT",profile["export_high_rate"]
    elif standard:
        exp_id,exp_name,exp_rate="standard","Standard FiT",profile["export_standard_rate"]
    else:
        exp_id,exp_name,exp_rate="fallback","Other export FiT",profile["export_fallback_rate"]
    exp={
        "id":exp_id,"name":exp_name,"rate":exp_rate,
        "high_window":high,
        "potential_high_rate":profile["export_high_rate"],
    }
    return imp,exp


def tax_adjustment(base,profile,component):
    """Signed additional amount on top of user-entered component amount.

    If GST is marked included, the line-item rate is already gross and no
    second GST is added. Other tax is always an additional percentage and
    should only be enabled if contract says so. For export credits (positive
    base), a positive adjustment raises credit; for negative export fees it
    increases the fee magnitude. Net amount subtracts all export credits.
    """
    gst=profile["gst_percent"]/100 if (
        profile["gst_mode"]=="exclusive" and
        profile[f"gst_on_{component}"]) else 0.0
    other=profile["other_tax_percent"]/100 if profile[
        f"other_tax_on_{component}"] else 0.0
    return base*(gst+other)


def priced_slice(imp_kwh,exp_kwh,seconds,profile,when):
    """Return signed costs/credits for observed interval at given local time."""
    imp_band,exp_band=choose_rates(profile,when)
    imp_base=imp_kwh*imp_band["rate"]
    exp_base=exp_kwh*exp_band["rate"]
    supply_base=seconds/86400*profile["daily_supply"]
    import_tax=tax_adjustment(imp_base,profile,"import")
    export_tax=tax_adjustment(exp_base,profile,"export")
    supply_tax=tax_adjustment(supply_base,profile,"supply")
    potential=0.0
    if exp_band["high_window"] and profile["high_fit_eligibility"]=="battery_only_unverified":
        higher=exp_kwh*(profile["export_high_rate"]-profile["export_standard_rate"])
        potential=higher+tax_adjustment(
            exp_kwh*profile["export_high_rate"],profile,"export"
        )-tax_adjustment(exp_base,profile,"export")
    return {
        "import_cost":imp_base+import_tax,
        "export_credit":exp_base+export_tax,
        "supply_cost":supply_base+supply_tax,
        "tax_adjustment":import_tax-export_tax+supply_tax,
        "net_cost":imp_base+import_tax-exp_base-export_tax+supply_base+supply_tax,
        "import_band":imp_band,
        "export_band":exp_band,
        "high_fit_unverified_difference":potential,
    }


def iter_minute_slices(start,end,tz):
    """Yield UTC-aware sub-intervals ending at each minute/local tariff boundary.

    Meter readings span up to 60 seconds. Minute splits also split local
    midnight and DST changes; midpoint is converted to actual local wall time.
    """
    cursor=start
    while cursor<end:
        epoch=cursor.timestamp()
        next_minute=datetime.fromtimestamp(
            (math.floor(epoch/60)+1)*60,timezone.utc)
        next_end=min(end,next_minute)
        if next_end<=cursor:
            break
        midpoint=cursor+(next_end-cursor)/2
        yield cursor,next_end,midpoint.astimezone(tz)
        cursor=next_end


def price_power_interval(start,end,start_power_w,end_power_w,profile,tz,split_fn):
    """Price actual positive-import/negative-export watts by local minute/rule.

    Linear interpolation of W over a short sample interval; each sub-slice is
    integrated with sign-crossing handling. Never interpolate a missing hour.
    """
    total_seconds=(end-start).total_seconds()
    if not 0<total_seconds<=60:
        return []
    result=[]
    for a,b,local_mid in iter_minute_slices(start,end,tz):
        fraction_a=(a-start).total_seconds()/total_seconds
        fraction_b=(b-start).total_seconds()/total_seconds
        pa=start_power_w+(end_power_w-start_power_w)*fraction_a
        pb=start_power_w+(end_power_w-start_power_w)*fraction_b
        duration=(b-a).total_seconds()
        imp,exp=split_fn(pa,pb,duration)
        priced=priced_slice(imp,exp,duration,profile,local_mid)
        result.append({
            "start":a,"end":b,"local":local_mid,"seconds":duration,
            "import_kwh":imp,"export_kwh":exp,**priced,
        })
    return result
