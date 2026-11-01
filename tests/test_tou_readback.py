"""Offline read-only TOU decoding tests. No device access or register writes."""
import unittest
from control_core.tou_readback import (
    decode_tou, diff_device_configs, UnverifiedMapping,
)

def clock(h, m):
    return (h << 8) | m

def sample():
    charge = [0, 1] + [0] * 21  # one discharge slot enabled
    discharge = [0] * 21
    discharge[:3] = [clock(22, 0), clock(22, 40), (4 << 8) | 99]
    return charge, discharge

class TestTOU(unittest.TestCase):
    def test_seven_slots_separately_and_fallback(self):
        charge, discharge = sample()
        config = decode_tou(charge, discharge, 1, 1)
        self.assertEqual(config.operating_mode_label(), "Time-of-use")
        self.assertEqual(config.fallback_label(), "Self-consumption")
        self.assertEqual(len(config.charge_slots), 7)
        self.assertEqual(len(config.discharge_slots), 7)
        self.assertTrue(config.discharge_slots[0].enabled)
        self.assertEqual(config.discharge_slots[0].start, "22:00")
        self.assertEqual(config.discharge_slots[0].end, "22:40")
        self.assertEqual(config.discharge_slots[0].day_mask_raw, 4)
        self.assertEqual(config.discharge_slots[0].power_percent_raw, 99)
        self.assertFalse(config.mapping_verified)  # needs live app parity check

    def test_zero_charge_and_zero_discharge_is_valid(self):
        charge = [0, 0] + [0] * 21
        discharge = [0] * 21
        device = decode_tou(charge, discharge, 1, 1)
        self.assertEqual(sum(s.enabled for s in device.charge_slots), 0)
        self.assertEqual(sum(s.enabled for s in device.discharge_slots), 0)
        self.assertEqual(len(device.charge_slots), 7)
        self.assertEqual(len(device.discharge_slots), 7)

    def test_all_seven_schedule_flags_allowed(self):
        charge, discharge = sample()
        charge[0], charge[1] = 127, 127
        device = decode_tou(charge, discharge, 1, 1)
        self.assertEqual(sum(s.enabled for s in device.charge_slots), 7)
        self.assertEqual(sum(s.enabled for s in device.discharge_slots), 7)

    def test_24_hour_clock_boundaries(self):
        charge, discharge = sample()
        discharge[0], discharge[1] = clock(0, 0), clock(23, 59)
        device = decode_tou(charge, discharge, 1, 1)
        self.assertEqual(device.discharge_slots[0].start, "00:00")
        self.assertEqual(device.discharge_slots[0].end, "23:59")

    def test_external_changes_are_detected(self):
        charge, discharge = sample()
        before = decode_tou(charge, discharge, 1, 1)
        discharge[0] = clock(23, 10)
        after = decode_tou(charge, discharge, 1, 0)
        changes = diff_device_configs(before, after)
        self.assertIn("discharge_slots", changes)
        self.assertIn("fallback_raw", changes)

    def test_unknown_flags_rejected(self):
        charge, discharge = sample()
        charge[0] = 1 << 7
        with self.assertRaises(UnverifiedMapping):
            decode_tou(charge, discharge, 1, 1)

    def test_bad_time_rejected(self):
        charge, discharge = sample()
        discharge[1] = clock(25, 0)
        with self.assertRaises(UnverifiedMapping):
            decode_tou(charge, discharge, 1, 1)

    def test_missing_words_rejected(self):
        charge, discharge = sample()
        with self.assertRaises(UnverifiedMapping):
            decode_tou(charge[:-1], discharge, 1, 1)

    def test_mode_3_is_not_selectable(self):
        charge, discharge = sample()
        result = decode_tou(charge, discharge, 3, 1)
        self.assertEqual(result.operating_mode_label(), "Other/unsupported")

if __name__ == "__main__":
    unittest.main()
