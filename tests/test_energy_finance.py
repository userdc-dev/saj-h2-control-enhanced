"""Offline tests for signed tariffs, zero crossings and HA metadata.

No Home Assistant import, no internet, no inverter. Extract pure functions
from energy_finance.py AST so CI can verify arithmetic without HA installed.
"""
import ast
import datetime
import math
from pathlib import Path
import unittest
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[1]
COMP=ROOT/"custom_components"/"saj_h2_control_enhanced"

def pure():
    source=ast.parse((COMP/"energy_finance.py").read_text())
    functions={"validate_pricing","split_grid_energy","estimate_cost",
               "estimate_benefit","snapshot_costs","local_period","_money"}
    nodes=[n for n in source.body if isinstance(n,ast.FunctionDef)
           and n.name in functions]
    module=ast.fix_missing_locations(ast.Module(body=nodes,type_ignores=[]))
    scope={"MAX_GAP_SECONDS":60,"datetime":datetime.datetime,"math":math}
    exec(compile(module,"energy_finance.py","exec"),scope)
    return scope

class EnergyFinanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.p=pure()

    def test_positive_import_and_negative_export_are_separate(self):
        f=self.p["split_grid_energy"]
        imported,exported=f(1000,1000,60)
        self.assertAlmostEqual(imported,1/60,places=7)
        self.assertEqual(exported,0)
        imported,exported=f(-2000,-2000,60)
        self.assertEqual(imported,0)
        self.assertAlmostEqual(exported,2/60,places=7)

    def test_zero_crossing_no_signed_cancellation(self):
        imp,exp=self.p["split_grid_energy"](1000,-1000,60)
        self.assertAlmostEqual(imp,1/240,places=7)
        self.assertAlmostEqual(exp,1/240,places=7)
        self.assertEqual(self.p["split_grid_energy"](1000,1000,120),(0,0))

    def test_signed_negative_import_and_export_prices(self):
        rates=self.p["validate_pricing"](-.10,-.20,1.00)
        self.assertEqual(rates,(-.10,-.20,1.00))
        cost=self.p["estimate_cost"](10,5,*rates)
        # 10 kWh importing earns $1, 5 kWh exporting costs $1,
        # plus $1 supply charge -> net $1 customer cost.
        self.assertEqual(cost,1.00)
        self.assertEqual(self.p["estimate_cost"](None,5,*rates),None)

    def test_savings_non_additive_baseline(self):
        fn=self.p["estimate_benefit"]
        self.assertEqual(fn(12,3,4,.5,.1),4.9)
        self.assertEqual(fn(None,3,4,.5,.1),None)
        self.assertEqual(fn(5,7,0,.5,.1),0)

    def test_full_daily_supply_is_independent_of_monitor_coverage(self):
        tz=ZoneInfo("Australia/Adelaide")
        now=datetime.datetime(2026,11,2,8,0,tzinfo=tz)
        row={"import_kwh":4,"export_kwh":2,"home_kwh":8,
             "solar_kwh":5,"battery_discharge_kwh":1,
             "coverage_seconds":7200,"legacy_supply_cost":1.5,
             "home_coverage_seconds":7200,
             "battery_discharge_coverage_seconds":7200}
        totals={
            "today":dict(row,period="2026-11-02"),
            "month":dict(row,period="2026-11"),
        }
        pricing={"import_rate":.5,"export_rate":.1,"daily_supply":1.5}
        out=self.p["snapshot_costs"](totals,pricing,now,tz)
        # Import $2 - export $0.20 + full daily supply $1.50
        self.assertEqual(out["today"]["net_cost"],3.30)
        self.assertEqual(out["month"]["net_cost"],3.30)
        self.assertTrue(out["today"]["period_partial"])
        self.assertEqual(out["today"]["self_supply_estimated_benefit"],2.2)

    def test_energy_labels_statistics_and_safety(self):
        sensor=(COMP/"sensor.py").read_text()
        for token in ("solar_production_energy","solar_production_power",
                      "battery_charged_energy","battery_discharged_energy",
                      "battery_state_of_charge","grid_import_energy_estimate",
                      "grid_export_energy_estimate","SajCostEstimateSensor"):
            self.assertIn(token,sensor)
        self.assertIn("SensorStateClass.TOTAL_INCREASING",sensor)
        self.assertIn("SensorStateClass.MEASUREMENT",sensor)
        finance=(COMP/"energy_finance.py").read_text()
        self.assertIn("Store(hass",finance)
        self.assertNotIn("write_register",finance)
        init=(COMP/"__init__.py").read_text()
        self.assertIn('"save_cost_settings"',init)
        self.assertIn('"write_sent":False',init)
        self.assertIn("safe_coordinator.async_add_listener",init)

    def test_forecast_uses_bounded_measured_learning(self):
        text=(COMP/"forecast.py").read_text()
        for term in ("learned_hours","_finalize_learning","_persist_learning",
                     "self._coverage<2700","self._peak_soc>=97",
                     "self._kwh_actual/expected","0.65","1.15"):
            self.assertIn(term,text)
        self.assertNotIn("write_register",text)

if __name__=="__main__":
    unittest.main()
