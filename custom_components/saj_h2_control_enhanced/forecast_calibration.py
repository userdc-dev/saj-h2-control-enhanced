"""Pure historic PV calibration and out-of-sample scoring. No HA or Modbus.

Historical reanalysis is a *hindcast*, not an archived weather forecast.
Refuse to apply a calibration unless it beats the uncorrected physical model
on a chronological holdout. Older HA long-term statistics are hourly means,
not exact metered energy; label estimates accordingly.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
import math
from statistics import mean
from zoneinfo import ZoneInfo

MIN_TRAIN = 20
MIN_TEST = 8
MIN_BIN = 3
MIN_MODEL_IMPROVEMENT = 0.02  # at least 2% out-of-sample MAE improvement
MAX_RECALIBRATION_FACTOR = 1.15
MIN_RECALIBRATION_FACTOR = 0.65


def finite(value):
    try:
        n = float(value)
        return math.isfinite(n)
    except (ValueError, TypeError, OverflowError):
        return False


def season(month: int, latitude: float) -> str:
    """Meteorological seasons; automatically flip for southern hemisphere."""
    northern = ("winter", "spring", "summer", "autumn")[
        ((int(month) % 12) // 3)
    ]
    if float(latitude) < 0:
        return {"winter": "summer", "spring": "autumn",
                "summer": "winter", "autumn": "spring"}[northern]
    return northern


def timestamp(row):
    """HA statistics Python/API can expose datetimes or epoch seconds/ms."""
    item = row.get("start")
    if isinstance(item, datetime):
        return int(item.timestamp())
    if isinstance(item, str):
        try:
            return int(datetime.fromisoformat(item.replace("Z","+00:00")).timestamp())
        except ValueError:
            return None
    if not finite(item):
        return None
    ts = float(item)
    if ts > 1e11:  # websocket epoch milliseconds
        ts /= 1000
    return int(ts) if ts > 0 else None


def stats_by_hour(rows, stat_type="mean"):
    """Map UTC hour start => guarded scalar, deduplicating by hour."""
    result = {}
    for row in rows or []:
        stamp = timestamp(row)
        if stamp is None or stamp % 3600 != 0:
            continue
        value = row.get(stat_type)
        if not finite(value):
            continue
        result[stamp] = float(value)
    return result


def weather_baseline(groups, efficiency, series, epoch):
    """Physical model kWh for an hourly GTI sample (hour BEGINNING epoch).

    The PV model uses kWp * historical tilted irradiance / 1000 * efficiency.
    No AC clipping: the user's battery may be charged on the DC bus.
    """
    if len(groups) != len(series) or not groups:
        return None
    total = 0.0
    clouds = []
    for group, observations in zip(groups, series):
        sample = observations.get(epoch)
        if not sample or len(sample) < 2:
            return None
        irradiance, cloud = sample[:2]
        if not finite(irradiance) or not finite(cloud):
            return None
        if not 0 <= float(irradiance) <= 1500 or not 0 <= float(cloud) <= 100:
            return None
        total += (float(group["count"]) * float(group["watts"]) *
                  float(irradiance) / 1_000_000) * float(efficiency)/100
        clouds.append(float(cloud))
    return total, mean(clouds)


def eligible_samples(power_stats, soc_stats, groups, efficiency,
                     archive_series, tz, latitude):
    """Conservative annual-season hourly sample candidates.

    HA's hourly mean power is treated as *approximate* hourly kWh (W / 1000).
    An unavailable SOC maximum cannot prove lack of curtailment, so never
    train on such a sample; summary makes this exclusion explicit.
    """
    power = stats_by_hour(power_stats)
    soc = stats_by_hour(soc_stats, "max")
    summary = {"power_stat_hours":len(power), "soc_stat_hours":len(soc),
               "weather_matched":0, "eligible_hours":0,
               "excluded_missing_soc":0, "excluded_curtailed":0,
               "excluded_clouds_or_low_irradiance":0,
               "excluded_outliers":0}
    samples=[]
    for epoch, watts in sorted(power.items()):
        baseline = weather_baseline(groups,efficiency,archive_series,epoch)
        if baseline is None:
            continue
        summary["weather_matched"]+=1
        expected,cloud=baseline
        if expected<0.7 or cloud>25 or watts<0:
            summary["excluded_clouds_or_low_irradiance"]+=1
            continue
        soc_max=soc.get(epoch)
        if soc_max is None or not 0<=soc_max<=100:
            summary["excluded_missing_soc"]+=1
            continue
        if soc_max>=97:
            summary["excluded_curtailed"]+=1
            continue
        observed=watts/1000  # hourly mean W => approximate 1h kWh
        ratio=observed/expected
        if not 0.45<=ratio<=1.55:
            summary["excluded_outliers"]+=1
            continue
        local=datetime.fromtimestamp(epoch,timezone.utc).astimezone(tz)
        samples.append({"epoch":epoch,"date":local.date().isoformat(),
                        "month":local.month,"season":season(local.month,latitude),
                        "hour":local.hour,"base":expected,"actual":observed,
                        "ratio":ratio})
    summary["eligible_hours"]=len(samples)
    return samples,summary


def _fit(samples):
    """Blend sparse samples toward 1.0; do not extrapolate to other hours."""
    bins=defaultdict(list)
    hours=defaultdict(list)
    for item in samples:
        bins[f'{item["season"]}:{item["hour"]}'].append(item["ratio"])
        hours[f'hour:{item["hour"]}'].append(item["ratio"])
    fit={}
    for key,values in bins.items():
        if len(values)<MIN_BIN:
            continue
        ratio=mean(values)
        weight=len(values)/(len(values)+8)
        fit[key]=max(MIN_RECALIBRATION_FACTOR,
                     min(MAX_RECALIBRATION_FACTOR,1+(ratio-1)*weight))
    for key,values in hours.items():
        if len(values)<MIN_BIN+1:
            continue
        ratio=mean(values)
        weight=len(values)/(len(values)+10)
        fit[key]=max(MIN_RECALIBRATION_FACTOR,
                     min(MAX_RECALIBRATION_FACTOR,1+(ratio-1)*weight))
    return {k:round(v,4) for k,v in fit.items()}


def factor_for(factors, season_name, hour):
    return float(factors.get(f"{season_name}:{hour}",
             factors.get(f"hour:{hour}",1.0)))


def _mae(samples,factors):
    if not samples:
        return None
    return mean(abs(p["actual"]-p["base"]*factor_for(
        factors,p["season"],p["hour"])) for p in samples)


def score_history(samples,summary):
    """Chronological holdout for promotion; no random train/test leakage."""
    samples=sorted(samples,key=lambda item:item["epoch"])
    meta=dict(summary)
    meta.update({"status":"Insufficient qualifying history","approved":False,
                 "train_hours":0,"holdout_hours":0,
                 "base_mae_kwh":None,"corrected_mae_kwh":None,
                 "improvement_percent":None,"factors":{},
                 "seasonal_hours":{}})
    if len(samples)<MIN_TRAIN+MIN_TEST:
        return meta
    train_end=max(MIN_TRAIN,int(len(samples)*.7))
    train,test=samples[:train_end],samples[train_end:]
    if len(test)<MIN_TEST:
        return meta
    draft=_fit(train)
    before=_mae(test,{})
    after=_mae(test,draft)
    improvement=(before-after)/before*100 if before and after is not None else 0
    approved=bool(draft and before and after is not None and
                  improvement>=MIN_MODEL_IMPROVEMENT*100)
    factors=_fit(samples) if approved else {}
    counts=defaultdict(int)
    for p in samples:
        counts[p["season"]]+=1
    meta.update({
        "status":"Validated calibration applied" if approved else
                 "Historical calibration held back (no measured improvement)",
        "approved":approved,"train_hours":len(train),
        "holdout_hours":len(test),
        "base_mae_kwh":round(before,3) if before is not None else None,
        "corrected_mae_kwh":round(after,3) if after is not None else None,
        "improvement_percent":round(improvement,1),
        "factors":factors,
        "seasonal_hours":dict(sorted(counts.items())),
        "first_date":samples[0]["date"],
        "last_date":samples[-1]["date"],
        "notes":"Retrospective reanalysis comparison, not issued-forecast accuracy. Hourly mean W approximates energy; incomplete hours may bias results.",
    })
    return meta


def evaluate_issued_forecasts(predictions,power_stats,tz,now=None):
    """Evaluate real forecasts SAVED BEFORE their target date using HA stats.

    No backfilling predictions. Require >=9 daytime hourly values spanning
    morning and afternoon to avoid awarding false skill for partial days.
    """
    now=now or datetime.now(timezone.utc)
    latest_date=now.astimezone(tz).date()
    actual_map=stats_by_hour(power_stats)
    days=defaultdict(dict)
    for epoch,watts in actual_map.items():
        local=datetime.fromtimestamp(epoch,timezone.utc).astimezone(tz)
        if 7<=local.hour<=18:
            days[local.date().isoformat()][local.hour]=watts
    results=[]
    seen_dates=set()
    for p in sorted(predictions,key=lambda r:r.get("issued_at","")):
        day=str(p.get("target_date",""))
        if day in seen_dates:
            continue
        try:
            target=datetime.fromisoformat(day).date()
            issued=datetime.fromisoformat(str(p.get("issued_at")).replace("Z","+00:00"))
            if issued.tzinfo is None or issued.astimezone(tz).date()>=target or target>=latest_date:
                continue
            estimate=float(p["predicted_kwh"])
        except (ValueError,TypeError,KeyError):
            continue
        hours=days.get(day,{})
        if len(hours)<9 or min(hours)>8 or max(hours)<16:
            continue
        # Only daytime readings (07:00–18:59) are included. The tail
        # outside these hours can be material in long summer days: label
        # the metric daytime coverage, not a certified full-day total.
        observed=sum(max(0,v) for v in hours.values())/1000
        results.append({"date":day,"issued_at":p["issued_at"],
                        "forecast_kwh":round(estimate,2),
                        "observed_daytime_kwh":round(observed,2),
                        "absolute_error_kwh":round(abs(estimate-observed),2),
                        "daytime_hours":len(hours)})
        seen_dates.add(day)
    results=results[-45:]
    return {
        "days_scored":len(results),
        "mae_kwh":round(mean(r["absolute_error_kwh"] for r in results),2)
                   if results else None,
        "recent":results[-7:],
        "status":"Tracking issued forecasts" if len(results)>=3 else
                 "Awaiting at least three complete days",
        "limitation":"Issued previous-day forecast vs observed 07:00–18:59 kWh from hourly means; NOT full-day metered energy. No historic forecasts invented.",
    }
