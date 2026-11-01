"""Offline tests for installable HA integration's standalone TOU decoder.

Can run without Home Assistant or pymodbus by importing protocol via path.
No inverter/network access. All register snapshots are synthetic or previously
read-only observed values.
"""
import importlib.util
from pathlib import Path
import unittest

PATH = (Path(__file__).resolve().parents[1] /
        "custom_components/saj_h2_control_enhanced/tou_protocol.py")
spec = importlib.util.spec_from_file_location("tou_protocol_under_test", PATH)
module = importlib.util.module_from_spec(spec)
import sys
sys.modules[spec.name] = module
spec.loader.exec_module(module)


class TestHAMonitorProtocol(unittest.TestCase):
    def test_exact_observed_snapshot(self):
        charge = [0, 1, 5888, 5947, 2103, 0, 827, 6170] + [0] * 15
        discharge = [5632, 5672, 1074] + [0] * 18
        cfg = module.decode_config(charge, discharge, 1, 1)
        self.assertEqual(cfg.mode_text, "Time-of-use")
        self.assertEqual(cfg.fallback_text, "Self-consumption")
        self.assertEqual(len(cfg.charge_slots), 7)
        self.assertEqual(len(cfg.discharge_slots), 7)
        self.assertEqual(cfg.summary("charge"), [])
        self.assertEqual(len(cfg.summary("discharge")), 1)
        slot = cfg.summary("discharge")[0]
        self.assertEqual((slot["slot"], slot["start"], slot["end"]),
                         (1, "22:00", "22:40"))
        self.assertEqual(slot["weekday_mask_raw"], 4)
        self.assertEqual(slot["power_percent_raw"], 50)
        self.assertEqual(slot["power_watts_saj_display"], 4950)


    def test_confirmed_weekday_only(self):
        cfg = module.decode_config([0, 1]+[0]*21,
            [0x1600, 0x1628, 0x0432]+[0]*18, 1, 1)
        self.assertEqual(cfg.summary("discharge")[0]["weekday_verified"], "Wednesday")
        cfg2 = module.decode_config([0, 1]+[0]*21,
            [0x1600, 0x1628, 0x0732]+[0]*18, 1, 1)
        self.assertEqual(cfg2.summary("discharge")[0]["weekday_verified"], "Unverified")

    def test_ignore_changes_to_disabled_stale_slots(self):
        a = module.decode_config([0]*23, [0]*21, 1, 1)
        inactive = [0]*21
        inactive[2] = 99
        b = module.decode_config([0]*23, inactive, 1, 1)
        self.assertEqual(module.active_signature(a), module.active_signature(b))
        self.assertEqual(module.describe_changes(a, b), ())

    def test_track_actual_app_originated_changes(self):
        before = module.decode_config([0, 1]+[0]*21,
            [0x1600, 0x1628, 0x0464]+[0]*18, 0, 1)
        after = module.decode_config([0, 1]+[0]*21,
            [0x1600, 0x1628, 0x0432]+[0]*18, 1, 1)
        changes = module.describe_changes(before, after)
        self.assertTrue(any("Mode:" in x for x in changes))
        self.assertIn("Discharge slot 1 changed", changes)
        self.assertEqual(len(changes), 2)

    def test_zero_schedules_valid(self):
        cfg = module.decode_config([0] * 23, [0] * 21, 0, 1)
        self.assertFalse(cfg.summary("charge"))
        self.assertFalse(cfg.summary("discharge"))

    def test_max_seven_each(self):
        cfg = module.decode_config([127, 127]+[0]*21, [0]*21, 1, 1)
        self.assertEqual(len(cfg.summary("charge")), 7)
        self.assertEqual(len(cfg.summary("discharge")), 7)

    def test_inactive_slots_can_contain_stale_time(self):
        charge, discharge = [0, 0]+[65535]*21, [65535]*21
        cfg = module.decode_config(charge, discharge, 0, 1)
        self.assertEqual(cfg.summary("charge"), [])

    def test_invalid_active_time_is_rejected(self):
        charge, discharge = [0, 1]+[0]*21, [0]*21
        discharge[0] = 0x1960  # 25:96
        with self.assertRaises(module.InvalidTOUData):
            module.decode_config(charge, discharge, 1, 1)

    def test_overwide_masks_fail(self):
        charge, discharge = [0, 128]+[0]*21, [0]*21
        with self.assertRaises(module.InvalidTOUData):
            module.decode_config(charge, discharge, 1, 1)

    def test_disabled_writing_modes_still_readable(self):
        cfg = module.decode_config([0]*23, [0]*21, 2, 1)
        self.assertIn("unsupported", cfg.mode_text)


if __name__ == "__main__":
    unittest.main()
