"""Offline TOU tariff tests: local windows, signed prices, taxes and DST.

Only standard-library pure code is loaded; NO HA, network or inverter needed.
"""
from __future__ import annotations
from copy import deepcopy
from datetime import datetime, timezone, timedelta
import importlib.util
from pathlib import Path
import unittest
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parents[1]
COMP=ROOT/"custom_components"/"saj_h2_control_enhanced"


def tariff_module():
    spec=importlib.util.spec_from_file_location("saj_tariffs_pure",COMP/"tariffs.py")
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


T=tariff_module()
TZ=ZoneInfo("Australia/Adelaide")


def local(iso):
    return datetime.fromisoformat(iso).replace(tzinfo=TZ)


def split_grid(a,b,secs):
    if not 0<secs<=60:
        return 0.,0.
    if a*b>=0:
        wh=(a+b)*secs/7200000
        return max(0,wh),max(0,-wh)
    x=abs(a)/(abs(a)+abs(b))
    one=a*secs*x/7200000
    two=b*secs*(1-x)/7200000
    return max(0,one)+max(0,two),max(0,-one)+max(0,-two)


class TariffTests(unittest.TestCase):
    def setUp(self):
        self.profile=T.validate_profile(deepcopy(T.EXAMPLE_PROFILE))

    def test_example_morning_evening_peak_sponge_and_fallback(self):
        for hour,id_ in ((8,"peak"),(18,"peak"),(11,"sponge"),
                         (23,"offpeak"),(3,"offpeak"),(9,"default"),
                         (16,"default")):
            with self.subTest(hour=hour):
                imp,_=T.choose_rates(self.profile,local(f"2026-11-02T{hour:02d}:30"))
                self.assertEqual(imp["id"],id_)

    def test_weekends_and_overnight_start_day_membership(self):
        p=deepcopy(self.profile)
        p["import_bands"]=[
            {"id":"weekend","name":"Weekend","rate":-.03,
             "windows":[{"start":"22:00","end":"05:00","days":[5]}]},
        ]
        p=T.validate_profile(p)
        self.assertEqual(T.choose_rates(p,local("2026-11-07T23:30"))[0]["id"],"weekend")
        self.assertEqual(T.choose_rates(p,local("2026-11-08T03:30"))[0]["id"],"weekend")
        self.assertEqual(T.choose_rates(p,local("2026-11-09T03:30"))[0]["id"],"default")

    def test_overlap_between_peak_and_sponge_is_rejected(self):
        p=deepcopy(self.profile)
        p["import_bands"][2]["windows"][0]["start"]="08:30"
        with self.assertRaisesRegex(ValueError,"overlap"):
            T.validate_profile(p)
        p=deepcopy(self.profile)
        p["import_bands"][0]["windows"][0]["days"]=[]
        with self.assertRaisesRegex(ValueError,"weekdays"):
            T.validate_profile(p)

    def test_standard_fit_windows_and_export_fallback(self):
        p=deepcopy(self.profile)
        p["export_standard_windows"]=[
            {"start":"06:00","end":"09:00","days":[0,1,2,3,4,5,6]}]
        p["export_fallback_rate"]=-.04
        p["export_high_windows"]=[
            {"start":"18:00","end":"20:00","days":[0,1,2,3,4,5,6]}]
        p["high_fit_eligibility"]="all_exports"
        p=T.validate_profile(p)
        self.assertEqual(T.choose_rates(p,local("2026-11-02T07:00"))[1]["id"],
                         "standard")
        self.assertEqual(T.choose_rates(p,local("2026-11-02T12:00"))[1]["id"],
                         "fallback")
        self.assertEqual(T.choose_rates(p,local("2026-11-02T18:30"))[1]["id"],
                         "high")
        self.assertAlmostEqual(T.choose_rates(p,local("2026-11-02T12:00"))[1]["rate"],-.04)
        p["high_fit_eligibility"]="battery_only_unverified"
        # Do not apply high FiT without verified export-origin evidence.
        self.assertEqual(T.choose_rates(p,local("2026-11-02T18:30"))[1]["id"],
                         "standard")

    def test_overnight_week_wrap_catches_overlap(self):
        p=deepcopy(self.profile)
        p["import_bands"]=[
            {"id":"sunlate","name":"Sunday","rate":.12,
             "windows":[{"start":"23:00","end":"02:00","days":[6]}]},
            {"id":"mondayearly","name":"Monday","rate":.35,
             "windows":[{"start":"01:00","end":"04:00","days":[0]}]},
        ]
        with self.assertRaisesRegex(ValueError,"overlap"):
            T.validate_profile(p)

    def test_all_export_high_fit_must_be_confirmed(self):
        p=deepcopy(self.profile)
        when=local("2026-11-02T18:30")
        self.assertEqual(T.choose_rates(p,when)[1]["rate"],.05)
        quote=T.priced_slice(0,2,60,p,when)
        self.assertAlmostEqual(quote["export_credit"],.10)
        self.assertAlmostEqual(quote["high_fit_unverified_difference"],.40)
        p["high_fit_eligibility"]="all_exports"
        quote=T.priced_slice(0,2,60,p,when)
        self.assertAlmostEqual(quote["export_credit"],.5)
        self.assertEqual(quote["high_fit_unverified_difference"],0)

    def test_negative_import_export_and_gst(self):
        p=deepcopy(self.profile)
        p["import_bands"]=[]
        p.update({"default_import_rate":-.20,"export_standard_rate":-.10,
                  "export_high_windows":[],"daily_supply":1.0,
                  "gst_percent":10,"gst_mode":"exclusive",
                  "other_tax_percent":2,
                  "gst_on_import":True,"gst_on_export":True,
                  "gst_on_supply":True,
                  "other_tax_on_import":True,"other_tax_on_export":True,
                  "other_tax_on_supply":True})
        p=T.validate_profile(p)
        q=T.priced_slice(10,5,3600,p,local("2026-11-02T13:00"))
        self.assertAlmostEqual(q["import_cost"],-2.24)
        self.assertAlmostEqual(q["export_credit"],-.56)
        self.assertAlmostEqual(q["supply_cost"],1.12/24)
        self.assertAlmostEqual(q["net_cost"],-2.24-(-.56)+1.12/24)
        p["gst_mode"]="included"
        q=T.priced_slice(10,5,3600,p,local("2026-11-02T13:00"))
        self.assertAlmostEqual(q["net_cost"],-2.04-(-.51)+1.02/24)

    def test_negative_extra_levy_is_rebate(self):
        p=deepcopy(self.profile)
        p["gst_mode"]="included"
        p["other_tax_percent"]=-5
        p["export_high_windows"]=[]
        p=T.validate_profile(p)
        quote=T.priced_slice(1,0,60,p,local("2026-11-02T09:30"))
        self.assertAlmostEqual(quote["import_cost"],.35*.95)
        self.assertAlmostEqual(quote["supply_cost"],1.0*.95/1440)

    def test_dst_supply_charges_are_per_actual_calendar_day(self):
        p=deepcopy(self.profile)
        p["daily_supply"]=23.0
        p["other_tax_percent"]=0
        p["gst_mode"]="included"
        # Start of daylight saving in Adelaide: Sunday 2026-10-04 is 23h.
        quote=T.priced_slice(0,0,3600,p,local("2026-10-04T12:00"))
        self.assertAlmostEqual(quote["supply_cost"],1.0)
        # A normal 24-hour day prices the same one-hour sample at 23/24.
        normal=T.priced_slice(0,0,3600,p,local("2026-10-05T12:00"))
        self.assertAlmostEqual(normal["supply_cost"],23/24)

    def test_split_interval_at_peak_boundary(self):
        p=deepcopy(self.profile)
        p["configured"]=True
        # 06:59:30–07:00:30 straddles off-peak -> peak
        start=local("2026-11-02T06:59:30")
        end=local("2026-11-02T07:00:30")
        result=T.price_power_interval(start,end,3600,3600,p,TZ,split_grid)
        self.assertEqual(len(result),2)
        self.assertEqual([x["import_band"]["id"] for x in result],
                         ["offpeak","peak"])
        self.assertAlmostEqual(sum(x["import_kwh"] for x in result),.06)
        self.assertAlmostEqual(sum(x["import_cost"] for x in result),
                               .03*.24+.03*.52)

    def test_midnight_allocates_to_two_dates(self):
        start=local("2026-11-02T23:59:30")
        end=local("2026-11-03T00:00:30")
        parts=T.price_power_interval(start,end,-1000,-1000,
             self.profile,TZ,split_grid)
        self.assertEqual(len(parts),2)
        self.assertEqual([p["local"].date().isoformat() for p in parts],
                         ["2026-11-02","2026-11-03"])
        self.assertAlmostEqual(sum(p["export_kwh"] for p in parts),1/60)

    def test_dst_boundary_uses_actual_timezone_offsets(self):
        # Australia/Adelaide 2026-10-04 local clocks jump 02:00 -> 03:00.
        first=datetime(2026,10,3,15,29,30,tzinfo=timezone.utc)
        last=first+timedelta(seconds=60)
        parts=T.price_power_interval(first,last,1000,1000,
             self.profile,TZ,split_grid)
        self.assertAlmostEqual(sum(p["seconds"] for p in parts),60)
        self.assertAlmostEqual(sum(p["import_kwh"] for p in parts),1/60)
        self.assertTrue(all(part["local"].tzinfo is not None for part in parts))

    def test_invalid_prices_are_rejected_even_for_nan_and_bool(self):
        for bad in (float("nan"),float("inf"),True,101,-101):
            p=deepcopy(self.profile)
            p["default_import_rate"]=bad
            with self.subTest(bad=bad),self.assertRaises(ValueError):
                T.validate_profile(p)

    def test_read_only_service_ui_source(self):
        init=(COMP/"__init__.py").read_text()
        self.assertIn('"save_tariff_profile"',init)
        self.assertIn('validate_profile(json.loads(raw))',init)
        self.assertIn('accounting.on_tariff_changed()',init)
        js=(COMP/"frontend"/"saj-tou-dynamic-card.js").read_text()
        for token in ('service:"save_tariff_profile"','high_fit_eligibility',
                      'export_high_windows','gst_mode','import_bands',
                      '"Remove category"','"Every day"','"Weekdays"',
                      '"Weekend"','"Save complete electricity tariff"'):
            self.assertIn(token,js)
        self.assertNotIn("write_register", (COMP/"tariffs.py").read_text())


if __name__=="__main__":
    unittest.main()
