"""Offline coordinator-level tests for interval pricing and tariff revisions.

Executes production class with fake Home Assistant API; no network or inverter.
"""
import ast
import asyncio
from datetime import datetime as RealDateTime, timezone, timedelta
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import logging
import math
import unittest
from zoneinfo import ZoneInfo

BASE=Path(__file__).resolve().parents[1]/"custom_components"/"saj_h2_control_enhanced"


def load_tariffs():
    spec=importlib.util.spec_from_file_location("tariffs_for_accounting",BASE/"tariffs.py")
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


T=load_tariffs()
TZ=ZoneInfo("Australia/Adelaide")


class Time(RealDateTime):
    at=RealDateTime(2026,11,2,0,0,tzinfo=timezone.utc)

    @classmethod
    def now(cls,tz=None):
        return cls.at.astimezone(tz) if tz else cls.at.replace(tzinfo=None)


class Coordinator:
    def __init__(self,hass,logger,name):
        self.hass=hass
        self.data=None

    def async_set_updated_data(self,data):
        self.data=data


class FakeStore:
    records={}

    def __init__(self,hass,version,key):
        self.key=key

    async def async_load(self):
        return self.records.get(self.key)

    async def async_save(self,data):
        import copy
        self.records[self.key]=copy.deepcopy(data)


class FakeHass:
    config=SimpleNamespace(time_zone="Australia/Adelaide",currency="AUD")

    def async_create_task(self,coroutine):
        # Background tasks are not needed for these deterministic tests.
        coroutine.close()


def accounting_scope():
    tree=ast.parse((BASE/"energy_finance.py").read_text())
    nodes=[n for n in tree.body
           if (isinstance(n,ast.FunctionDef) or isinstance(n,ast.ClassDef))]
    namespace={
        "__name__":"energy_finance_test",
        "DataUpdateCoordinator":Coordinator,
        "Store":FakeStore,
        "_LOGGER":logging.getLogger("accounting_test"),
        "datetime":Time,"timezone":timezone,
        "monotonic":lambda:0,
        "math":math,
        "MAX_GAP_SECONDS":60,
        "DEFAULT_PRICING":{
            "import_rate":.35,"export_rate":.05,"daily_supply":1.0,
            "currency":"AUD","configured":False,
        },
        "EXAMPLE_PROFILE":T.EXAMPLE_PROFILE,
        "price_power_interval":T.price_power_interval,
        "choose_rates":T.choose_rates,
        "full_daily_supply":T.full_daily_supply,
    }
    exec(compile(ast.fix_missing_locations(ast.Module(nodes,[])),
                 "energy_finance.py","exec"),namespace)
    return namespace


class AccountingTests(unittest.TestCase):
    def setUp(self):
        FakeStore.records.clear()
        self.ns=accounting_scope()
        self.profile=T.validate_profile({
            **T.EXAMPLE_PROFILE,
            "configured":True,"daily_supply":0,
            "high_fit_eligibility":"all_exports",
        })
        self.entry=SimpleNamespace(
            entry_id="test_inverter",
            options={"tariff_profile":self.profile,"tariff_revision":"rev1"})
        self.monitor=SimpleNamespace(data={
            "grid_power":3600,
            "home_load_power":1000,
            "battery_power":0,
            "total_pv_power":0,
        })
        self.accounting=self.ns["SajEnergyAccounting"](
            FakeHass(),self.entry,self.monitor)

    def advance(self,seconds):
        Time.at=Time.at+timedelta(seconds=seconds)
        self.accounting.on_monitor_update()

    def test_price_ledger_is_not_rewritten_when_rate_changes(self):
        async def run():
            await self.accounting.async_initialize()
            Time.at=RealDateTime(2026,11,2,7,30,tzinfo=TZ).astimezone(timezone.utc)
            self.accounting.on_monitor_update()
            self.advance(30)
            row=self.accounting.totals["today"]
            first_cost=row["tariff"]["import_cost"]
            self.assertAlmostEqual(first_cost,0.03*.52,places=6)
            self.assertAlmostEqual(row["import_kwh"],0.03,places=6)
            first_kwh=row["tariff"]["import_kwh"]
            self.assertAlmostEqual(first_kwh,0.03)
            self.profile["import_bands"][0]["rate"]=.12
            self.entry.options["tariff_profile"]=self.profile
            self.entry.options["tariff_revision"]="rev2"
            self.accounting.on_tariff_changed()
            self.assertAlmostEqual(row["tariff"]["import_cost"],first_cost)
            self.advance(30)  # first post-save sample only creates anchor
            self.assertAlmostEqual(row["tariff"]["import_cost"],first_cost)
            self.advance(30)  # second post-save sample prices at .12
            self.assertAlmostEqual(row["tariff"]["import_cost"],
                                   first_cost+0.03*.12,places=6)
            self.assertAlmostEqual(row["tariff"]["import_kwh"],0.06,places=6)
            self.assertAlmostEqual(row["import_kwh"],0.06,places=6)
            await self.accounting.async_save()
            second=self.ns["SajEnergyAccounting"](
                FakeHass(),self.entry,self.monitor)
            await second.async_initialize()
            self.assertAlmostEqual(
                second.totals["today"]["tariff"]["import_cost"],
                first_cost+0.03*.12,places=6)
            self.assertAlmostEqual(
                second.totals["lifetime"]["import_kwh"],0.06,places=6)
        asyncio.run(run())

    def test_full_supply_is_charged_without_power_measurements(self):
        async def run():
            self.profile["daily_supply"]=1.4944
            self.profile["gst_mode"]="included"
            self.profile["other_tax_percent"]=0
            self.entry.options["tariff_profile"]=T.validate_profile(self.profile)
            Time.at=RealDateTime(2026,11,2,13,1,tzinfo=TZ).astimezone(timezone.utc)
            await self.accounting.async_initialize()
            day=self.accounting.totals["today"]["tariff"]
            month=self.accounting.totals["month"]["tariff"]
            self.assertAlmostEqual(day["supply_cost"],1.4944,places=6)
            self.assertAlmostEqual(day["net_cost"],1.4944,places=6)
            self.assertEqual(day["coverage_seconds"],0)
            self.assertAlmostEqual(month["supply_cost"],1.4944,places=6)
            cost=self.accounting.data["costs"]["today"]
            self.assertEqual(cost["net_cost"],1.49)
            self.assertEqual(cost["supply_days_charged"],1)
            # repeated telemetry does not re-charge the fixed fee
            for _ in range(5):
                self.advance(10)
            self.assertAlmostEqual(day["supply_cost"],1.4944,places=6)
            await self.accounting.async_save()
            replacement=self.ns["SajEnergyAccounting"](
                FakeHass(),self.entry,self.monitor)
            await replacement.async_initialize()
            self.assertAlmostEqual(
                replacement.totals["today"]["tariff"]["supply_cost"],
                1.4944,places=6)
        asyncio.run(run())

    def test_supply_not_double_charged_on_midday_tariff_edit(self):
        async def run():
            self.profile["daily_supply"]=1.5
            self.profile["gst_mode"]="included"
            self.profile["other_tax_percent"]=0
            self.entry.options["tariff_profile"]=T.validate_profile(self.profile)
            Time.at=RealDateTime(2026,11,2,10,0,tzinfo=TZ).astimezone(timezone.utc)
            await self.accounting.async_initialize()
            self.assertAlmostEqual(
                self.accounting.totals["today"]["tariff"]["supply_cost"],1.5)
            self.profile["daily_supply"]=2.5
            self.entry.options["tariff_profile"]=T.validate_profile(self.profile)
            self.entry.options["tariff_revision"]="rev2"
            self.accounting.on_tariff_changed()
            self.assertAlmostEqual(
                self.accounting.totals["today"]["tariff"]["supply_cost"],1.5)
            self.assertAlmostEqual(
                self.accounting.totals["month"]["tariff"]["supply_cost"],1.5)
            Time.at=RealDateTime(2026,11,3,8,0,tzinfo=TZ).astimezone(timezone.utc)
            self.accounting.on_monitor_update()
            self.assertAlmostEqual(
                self.accounting.totals["today"]["tariff"]["supply_cost"],2.5)
            self.assertAlmostEqual(
                self.accounting.totals["month"]["tariff"]["supply_cost"],4.0)
            self.assertEqual(len(
                self.accounting.totals["month"]["tariff"]["supply_charged_dates"]),2)
        asyncio.run(run())

    def test_legacy_flat_tariff_also_gets_full_daily_supply(self):
        async def run():
            self.entry.options={
                "configured":True,"import_rate":.35,
                "export_rate":.05,"daily_supply":1.49
            }
            Time.at=RealDateTime(2026,11,2,13,0,tzinfo=TZ).astimezone(timezone.utc)
            await self.accounting.async_initialize()
            today=self.accounting.data["costs"]["today"]
            self.assertEqual(today["supply_cost"],1.49)
            self.assertEqual(today["net_cost"],1.49)
            self.accounting.on_monitor_update()
            self.assertEqual(self.accounting.data["costs"]["today"]["supply_cost"],1.49)
            Time.at=RealDateTime(2026,11,3,13,0,tzinfo=TZ).astimezone(timezone.utc)
            self.accounting.on_monitor_update()
            self.assertEqual(self.accounting.data["costs"]["month"]["supply_cost"],2.98)
        asyncio.run(run())

    def test_upgrade_reconciles_current_day_prorated_fee(self):
        async def run():
            self.profile["daily_supply"]=1.5
            self.profile["gst_mode"]="included"
            self.profile["other_tax_percent"]=0
            self.entry.options["tariff_profile"]=T.validate_profile(self.profile)
            Time.at=RealDateTime(2026,11,2,11,0,tzinfo=TZ).astimezone(timezone.utc)
            old=self.ns["_new_tariff_ledger"]()
            old["coverage_seconds"]=1800
            old["supply_cost"]=0.03125
            old["net_cost"]=0.03125
            self.accounting.totals["today"]=self.ns["_new_period"]("2026-11-02")
            self.accounting.totals["month"]=self.ns["_new_period"]("2026-11")
            self.accounting.totals["today"]["tariff"]=dict(old)
            self.accounting.totals["month"]["tariff"]=dict(old)
            self.accounting._ensure_daily_supply(Time.at)
            self.assertAlmostEqual(
                self.accounting.totals["today"]["tariff"]["supply_cost"],1.5)
            self.assertAlmostEqual(
                self.accounting.totals["month"]["tariff"]["supply_cost"],1.5)
        asyncio.run(run())

    def test_import_and_export_have_independent_signed_ledger(self):
        async def run():
            self.profile["import_bands"]=[]
            self.profile["default_import_rate"]=-.25
            self.profile["export_high_windows"]=[]
            self.profile["export_standard_rate"]=-.10
            self.entry.options["tariff_profile"]=T.validate_profile(self.profile)
            await self.accounting.async_initialize()
            Time.at=RealDateTime(2026,11,2,14,0,tzinfo=TZ).astimezone(timezone.utc)
            self.monitor.data["grid_power"]=1200
            self.accounting.on_monitor_update()
            self.advance(30)
            row=self.accounting.totals["today"]["tariff"]
            self.assertLess(row["import_cost"],0)  # paid to import
            self.assertAlmostEqual(row["net_cost"],row["import_cost"])
            self.monitor.data["grid_power"]=-1200
            self.advance(30)  # sign crossing: both sides priced
            self.advance(30)
            row=self.accounting.totals["today"]["tariff"]
            self.assertGreater(row["export_kwh"],0)
            self.assertLess(row["export_credit"],0)  # export charge
            self.assertGreater(
                row["net_cost"],row["import_cost"])
        asyncio.run(run())


if __name__=="__main__":
    unittest.main()
