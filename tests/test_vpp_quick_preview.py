"""VPP preview is deterministic, bounded and cannot issue inverter writes."""
import ast
from datetime import datetime
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest
from zoneinfo import ZoneInfo

COMP=Path(__file__).resolve().parents[1]/"custom_components"/"saj_h2_control_enhanced"
spec=importlib.util.spec_from_file_location("vpp_quick_preview",COMP/"vpp_quick_preview.py")
vpp=importlib.util.module_from_spec(spec)
spec.loader.exec_module(vpp)
TZ=ZoneInfo("Australia/Adelaide")


def slot(number,enabled=False,start="08:00",end="09:00",mask=1,percent=50):
    return SimpleNamespace(number=number,enabled=enabled,start=start,end=end,
                           day_mask=mask,power_percent=percent)


def snapshot(mode=0,fallback=1,charge=None,discharge=None):
    charge=charge or [slot(i) for i in range(1,8)]
    discharge=discharge or [slot(i) for i in range(1,8)]
    return SimpleNamespace(mode=mode,fallback=fallback,
                           mode_text="Self-consumption" if mode==0 else "Time-of-use",
                           fallback_text="Self-consumption" if fallback==1 else "Standby",
                           charge_mask=sum(1<<(x.number-1) for x in charge if x.enabled),
                           discharge_mask=sum(1<<(x.number-1) for x in discharge if x.enabled),
                           charge_slots=charge,discharge_slots=discharge)


def preview(config=None,direction="charge",minutes=10,now=None,soc=50):
    return vpp.preview_dispatch(
        config or snapshot(), direction=direction,duration_minutes=minutes,
        now=now or datetime(2026,11,2,17,32,tzinfo=TZ),soc=soc)


class VPPPreviewTests(unittest.TestCase):
    def test_valid_readonly_preview_and_future_time(self):
        for minutes in (5,10,60):
            with self.subTest(minutes=minutes):
                report=preview(minutes=minutes)
                self.assertTrue(report["preflight_passed"])
                self.assertFalse(report["write_sent"])
                self.assertFalse(report["can_start"])
                self.assertFalse(report["live_activation_supported"])
                self.assertEqual(report["proposed_slot"],1)
                self.assertEqual(report["day_mask_raw"],1)
                self.assertEqual(report["requested_power_percent_raw"],100)
                begin=datetime.fromisoformat(report["planned_start_local"])
                end=datetime.fromisoformat(report["planned_end_local"])
                self.assertEqual(int((end-begin).total_seconds()/60),minutes)

    def test_overlap_blocks_any_direction(self):
        active=[slot(1,True,start="17:35",end="18:30")]+[
            slot(i) for i in range(2,8)]
        for direction in ("charge","discharge"):
            report=preview(snapshot(charge=active),direction=direction)
            self.assertFalse(report["preflight_passed"])
            self.assertTrue(any("overlaps" in x for x in report["blockers"]))

    def test_all_slots_occupied(self):
        full=[slot(i,True,start="08:00",end="09:00") for i in range(1,8)]
        r=preview(snapshot(discharge=full),direction="discharge")
        self.assertIsNone(r["proposed_slot"])
        self.assertTrue(any("All seven" in x for x in r["blockers"]))

    def test_soc_reserves_and_missing_soc(self):
        self.assertFalse(preview(soc=None)["preflight_passed"])
        self.assertFalse(preview(direction="charge",soc=96)["preflight_passed"])
        self.assertFalse(preview(direction="discharge",soc=5)["preflight_passed"])
        self.assertTrue(preview(direction="discharge",soc=50)["preflight_passed"])

    def test_standby_and_weekend_not_armed(self):
        report=preview(snapshot(fallback=0))
        self.assertTrue(any("Self-consumption" in x for x in report["blockers"]))
        saturday=datetime(2026,11,7,11,0,tzinfo=TZ)
        weekend=preview(now=saturday)
        self.assertFalse(weekend["preflight_passed"])
        self.assertTrue(any("Saturday" in x for x in weekend["blockers"]))

    def test_midnight_and_bad_input_blocked(self):
        now=datetime(2026,11,2,23,50,tzinfo=TZ)
        late=preview(now=now,minutes=60)
        self.assertTrue(any("midnight" in x for x in late["blockers"]))
        for bad in (0,1,6,30,120,"10",True):
            with self.assertRaises(ValueError):
                preview(minutes=bad)
        with self.assertRaises(ValueError):
            preview(direction="curtail")

    def test_not_connected_to_writes_or_timed_automation(self):
        code=(COMP/"vpp_quick_preview.py").read_text()
        self.assertNotIn("write_register",code)
        self.assertNotIn("asyncio.sleep",code)
        entry=(COMP/"__init__.py").read_text()
        self.assertIn('"preview_vpp_dispatch"',entry)
        self.assertIn("snapshot = await read_full(client)",entry)
        self.assertIn('"VPP_PREFLIGHT_ONLY"',code)
        self.assertNotIn('"start_vpp_dispatch"',entry)
        self.assertNotIn('"stop_vpp_dispatch"',entry)
        frontend=(COMP/"frontend"/"saj-tou-dynamic-card.js").read_text()
        self.assertIn('"Preview max charge"',frontend)
        self.assertIn('"Preview max discharge"',frontend)
        self.assertIn('"supervised_self_consumption_pilot"',frontend)
        self.assertNotIn('service:"start_vpp_dispatch"',frontend)


if __name__=="__main__":
    unittest.main()
