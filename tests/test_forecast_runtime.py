"""Offline SajEditableForecast runtime smoke with fake HA, no network/inverter."""
from __future__ import annotations

import ast
import asyncio
from datetime import datetime, timedelta, timezone
import importlib.util
import logging
from pathlib import Path
from types import SimpleNamespace
import unittest
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[1]/"custom_components"/"saj_h2_control_enhanced"
spec=importlib.util.spec_from_file_location("calibration_mock",ROOT/"forecast_calibration.py")
CAL=importlib.util.module_from_spec(spec)
spec.loader.exec_module(CAL)
SRC=(ROOT/"forecast.py").read_text()


class FakeCoordinator:
    def __init__(self,hass,logger,name,update_interval=None):
        self.hass=hass
        self.data={}
        self.last_update_success=True
    def async_set_updated_data(self,value):
        self.data=value


class FakeStore:
    saved={}
    def __init__(self,hass,version,key):
        self.key=key
    async def async_load(self):
        return self.saved.get(self.key)
    async def async_save(self,value):
        import copy
        self.saved[self.key]=copy.deepcopy(value)


def forecast_scope():
    parsed=ast.parse(SRC)
    nodes=[n for n in parsed.body if isinstance(n,(ast.ClassDef,ast.FunctionDef))]
    scope={
        "__name__":"forecast_fake",
        "DataUpdateCoordinator":FakeCoordinator,
        "Store":FakeStore,
        "_LOGGER":logging.getLogger("forecast_fake"),
        "datetime":datetime,"timedelta":timedelta,"timezone":timezone,
        "ZoneInfo":ZoneInfo,
        "DEFAULT_GROUPS":[
            {"count":10,"watts":400,"azimuth":0,"tilt":25}],
        "DEFAULT_EFFICIENCY":100,
        "DEFAULT_AC_LIMIT":10.0,
        "HISTORY_LOOKBACK_DAYS":180,
        "HISTORY_AUTO_RECHECK_DAYS":7,
        "eligible_samples":CAL.eligible_samples,
        "score_history":CAL.score_history,
        "evaluate_issued_forecasts":CAL.evaluate_issued_forecasts,
        "stats_by_hour":CAL.stats_by_hour,
        "factor_for":CAL.factor_for,
        "season":CAL.season,
        "finite":CAL.finite,
    }
    exec(compile(ast.fix_missing_locations(ast.Module(nodes,[])),
                 "forecast.py","exec"),scope)
    return scope


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        FakeStore.saved.clear()
        self.scope=forecast_scope()
        group={"count":10,"watts":400,"azimuth":0,"tilt":25}
        entry=SimpleNamespace(entry_id="test_001",options={
            "forecast_groups":[group],
            "forecast_efficiency":100,
            "forecast_ac_limit_kw":10,
            "forecast_configured":True
        })
        self.entry=entry
        self.hass=SimpleNamespace(
            config=SimpleNamespace(time_zone="Australia/Adelaide",
                                   latitude=-34.8,longitude=138.5),
            async_create_task=lambda coro:coro.close()
        )
        self.forecast=self.scope["SajEditableForecast"](self.hass,entry)

    def _good_rows(self):
        anchor=int(datetime(2026,6,1,tzinfo=timezone.utc).timestamp())
        stamps=[anchor+day*86400+hour*3600
                for day in range(20) for hour in (0,1,2,3)]
        pv=[{"start":t,"mean":3400} for t in stamps]
        soc=[{"start":t,"max":70} for t in stamps]
        archive=[{t:(1000,10) for t in stamps}]
        return pv,soc,archive

    def test_backfill_persists_only_if_holdout_improves(self):
        async def run():
            pv,soc,weather=self._good_rows()
            async def stats(_days):
                return pv,soc,"sensor.saj_h2_safe_monitor_total_solar_power"
            async def archives(_start,_end,_groups):
                return weather
            self.forecast._recorder_stats=stats
            self.forecast._archive_weather=archives
            result=await self.forecast.async_backfill_history(180,force=True)
            self.assertTrue(result["approved"])
            self.assertGreater(result["eligible_hours"],28)
            self.assertTrue(self.forecast.seasonal_factors)
            self.assertGreater(
                self.forecast._hour_factor(pv[0]["start"]),.65)
            self.assertLess(
                self.forecast._hour_factor(pv[0]["start"]),1)
            self.assertIn("seasonal_factors",next(iter(FakeStore.saved.values())))
            skipped=await self.forecast.async_backfill_history(180,force=False)
            self.assertEqual(skipped["status"],"Recently scanned")
            fresh=self.scope["SajEditableForecast"](self.hass,self.entry)
            await fresh.async_load_learning()
            self.assertEqual(fresh.seasonal_factors,self.forecast.seasonal_factors)
            self.assertTrue(fresh.history_calibration["approved"])
        asyncio.run(run())

    def test_lacking_soc_history_does_not_activate_bias(self):
        async def run():
            pv,soc,weather=self._good_rows()
            async def stats(_days):
                return pv,[],"sensor.test_solar"
            self.forecast._recorder_stats=stats
            self.forecast._archive_weather=lambda *args:None
            result=await self.forecast.async_backfill_history(180,force=True)
            self.assertFalse(result["approved"])
            self.assertEqual(self.forecast.seasonal_factors,{})
            self.assertEqual(self.forecast.history_calibration["soc_stat_hours"],0)
            self.assertEqual(self.forecast._hour_factor(pv[0]["start"]),1.0)
        asyncio.run(run())

    def test_bad_days_rejected_without_forecast_or_modbus_changes(self):
        async def run():
            with self.assertRaises(ValueError):
                await self.forecast.async_backfill_history(400,force=True)
            self.assertNotIn("write_register",SRC)
            self.assertNotIn("AsyncModbusTcpClient",SRC)
        asyncio.run(run())


if __name__=="__main__":
    unittest.main()
