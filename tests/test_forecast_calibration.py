"""Pure solar calibration test cases. No Home Assistant or live weather calls."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import importlib.util
from pathlib import Path
import unittest
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[1]
COMP=ROOT/"custom_components"/"saj_h2_control_enhanced"
spec=importlib.util.spec_from_file_location("forecast_calibration_pure",COMP/"forecast_calibration.py")
CAL=importlib.util.module_from_spec(spec)
spec.loader.exec_module(CAL)
TZ=ZoneInfo("Australia/Adelaide")
GROUPS=[{"count":10,"watts":400,"azimuth":0,"tilt":25}]


def stats(epoch,watts,soc=65):
    return {"start":epoch,"mean":watts},{"start":epoch,"max":soc}


class ForecastLearningTests(unittest.TestCase):
    def test_season_hemisphere(self):
        self.assertEqual(CAL.season(12,-34.8),"summer")
        self.assertEqual(CAL.season(6,-34.8),"winter")
        self.assertEqual(CAL.season(9,-34.8),"spring")
        self.assertEqual(CAL.season(3,52.0),"spring")
        self.assertEqual(CAL.season(1,52.0),"winter")

    def test_physical_power_units_and_hour_start_alignment(self):
        epoch=1760000400
        weather=[{epoch:(750,10)}]
        base,cloud=CAL.weather_baseline(GROUPS,87,weather,epoch)
        self.assertAlmostEqual(base,2.61,places=2)
        self.assertEqual(cloud,10)
        self.assertIsNone(CAL.weather_baseline(GROUPS,87,weather,epoch+3600))
        self.assertIsNone(CAL.weather_baseline(GROUPS,87,[{epoch:(None,10)}],epoch))

    def test_retrospective_filters_missing_soc_full_battery_and_cloud(self):
        origin=int(datetime(2026,9,1,tzinfo=timezone.utc).timestamp())
        power=[];soc=[];weather={}
        for i in range(6):
            epoch=origin+i*3600
            power.append({"start":epoch,"mean":2500})
            if i!=1:soc.append({"start":epoch,"max":99 if i==2 else 50})
            weather[epoch]=(900,75 if i==3 else 8)
        power[-1]["mean"]=30000 # implausibly above modeled 3.1 kWh
        samples,meta=CAL.eligible_samples(
            power,soc,GROUPS,87,[weather],TZ,-34)
        self.assertEqual(len(samples),2)
        self.assertEqual(meta["excluded_missing_soc"],1)
        self.assertEqual(meta["excluded_curtailed"],1)
        self.assertEqual(meta["excluded_clouds_or_low_irradiance"],1)
        self.assertEqual(meta["excluded_outliers"],1)

    def test_validate_seasonal_correction_using_chronological_holdout(self):
        origin=int(datetime(2026,9,1,tzinfo=timezone.utc).timestamp())
        # Repeated daytime hours over multiple weeks; observed consistently
        # 15% below physical model. Holdout must show measurable improvement.
        samples=[]
        for i in range(80):
            epoch=origin+int(i/4)*86400+(i%4)*3600+9*3600
            local=datetime.fromtimestamp(epoch,timezone.utc).astimezone(TZ)
            samples.append({
                "epoch":epoch,"date":local.date().isoformat(),
                "season":CAL.season(local.month,-34),
                "hour":local.hour,"base":4,"actual":3.4,
                "ratio":0.85,
            })
        result=CAL.score_history(samples,{"eligible_hours":80})
        self.assertTrue(result["approved"])
        self.assertLess(result["corrected_mae_kwh"],result["base_mae_kwh"])
        self.assertGreater(result["improvement_percent"],2)
        self.assertTrue(result["factors"])
        self.assertTrue(all(0.65<=f<=1.15 for f in result["factors"].values()))

    def test_do_not_deploy_regressive_model_or_sparse_history(self):
        start=int(datetime(2026,9,1,tzinfo=timezone.utc).timestamp())
        # Training biased low, holdout biased high: learned correction hurts
        # later dates, so it must not be promoted.
        data=[]
        for i in range(80):
            epoch=start+i*86400
            local=datetime.fromtimestamp(epoch,timezone.utc).astimezone(TZ)
            actual=3 if i<56 else 4
            data.append({"epoch":epoch,"date":local.date().isoformat(),
                         "season":CAL.season(local.month,-34),
                         "hour":10,"base":4,"actual":actual,
                         "ratio":actual/4})
        result=CAL.score_history(data,{"eligible_hours":80})
        self.assertFalse(result["approved"])
        self.assertEqual(result["factors"],{})
        self.assertFalse(CAL.score_history(data[:10],{})["approved"])

    def test_issued_forecast_scored_only_after_day_with_matching_hours(self):
        target=datetime(2026,10,20,tzinfo=TZ)
        records=[]
        for hour in range(6,18):
            # HA UTC-aligned intervals start at xx:30 local and their
            # physical midpoint is the next local whole hour (07..18).
            epoch=int(target.replace(hour=hour,minute=30).timestamp())
            records.append({"start":epoch,"mean":1000.0})
        predictions=[
            {"issued_at":"2026-10-19T09:00:00+00:00",
             "target_date":"2026-10-20",
             "predicted_daytime_kwh":12.5,
             "predicted_kwh":200}, # must NOT use unrelated 200-kWh full day
            {"issued_at":"2026-10-21T01:00:00+00:00",
             "target_date":"2026-10-21",
             "predicted_daytime_kwh":20},
        ]
        scored=CAL.evaluate_issued_forecasts(
            predictions,records,TZ,
            now=datetime(2026,10,25,tzinfo=timezone.utc))
        self.assertEqual(scored["days_scored"],1)
        self.assertEqual(scored["recent"][0]["forecast_daytime_kwh"],12.5)
        self.assertEqual(scored["recent"][0]["observed_daytime_kwh"],12)
        self.assertEqual(scored["mae_kwh"],0.5)
        # Cannot synthesize a forecast after target has started
        self.assertTrue(scored["recent"][0]["issued_at"]<"2026-10-20")

    def test_missing_daytime_recording_wont_produce_false_accuracy(self):
        target=datetime(2026,10,20,tzinfo=TZ)
        rows=[
            {"start":int(target.replace(hour=h,minute=30).timestamp()),"mean":1000}
            for h in range(12,15)
        ]
        preds=[{"issued_at":"2026-10-19T03:00:00+00:00",
                "target_date":"2026-10-20","predicted_daytime_kwh":12}]
        scored=CAL.evaluate_issued_forecasts(
            preds,rows,TZ,now=datetime(2026,10,25,tzinfo=timezone.utc))
        self.assertEqual(scored["days_scored"],0)
        self.assertIsNone(scored["mae_kwh"])

    def test_readonly_and_ha_stats_integration_contract(self):
        forecast=(COMP/"forecast.py").read_text()
        init=(COMP/"__init__.py").read_text()
        ui=(COMP/"frontend"/"saj-tou-dynamic-card.js").read_text()
        self.assertIn("statistics_during_period",forecast)
        self.assertIn("ARCHIVE_URL",forecast)
        self.assertIn("int(ts)-3600:(value,cloud)",forecast)
        self.assertIn("start_epoch+1800",forecast)
        self.assertIn("epoch+1800", (COMP/"forecast_calibration.py").read_text())
        self.assertIn("async_backfill_history",forecast)
        self.assertIn("seasonal_factors",forecast)
        self.assertIn("_save_issued_forecast",forecast)
        self.assertIn("entry.async_on_unload(async_track_time_interval(",init)
        self.assertIn('"scan_forecast_history"',init)
        self.assertIn('"write_sent":False',init)
        self.assertIn('service:"scan_forecast_history"',ui)
        for unsafe in ("write_register","AsyncModbusTcpClient",
                       "write_holding_register"):
            self.assertNotIn(unsafe,forecast)
            self.assertNotIn(unsafe,(COMP/"forecast_calibration.py").read_text())


if __name__=="__main__":
    unittest.main()
