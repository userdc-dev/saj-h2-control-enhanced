"""Offline tests for single-slot SAJ schedule dry-run validation."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest

path = Path("custom_components/saj_h2_control_enhanced/schedule_preview.py")
spec = importlib.util.spec_from_file_location("saj_schedule_preview", path)
mod = importlib.util.module_from_spec(spec)
import sys
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)

def slot(start="22:00", end="22:40", mask=16, power=70, enabled=True):
    return SimpleNamespace(
        start=start,end=end,day_mask=mask,power_percent=power,enabled=enabled
    )

def config():
    charge=[slot()]+[slot(enabled=False) for _ in range(6)]
    discharge=[slot(mask=4,power=50)]+[slot(enabled=False) for _ in range(6)]
    return SimpleNamespace(
        mode=1,fallback=1,charge_mask=1,discharge_mask=1,
        charge_slots=charge,discharge_slots=discharge,
    )

class SchedulePreviewTests(unittest.TestCase):
    def plan(self, **changes):
        args={
            "direction":"charge","slot_number":1,
            "expected":mod.SlotValue("22:00","22:40",16,70),
            "new_start":"21:30","new_end":"22:00",
            "days":["Mon","Fri"],"power_percent":50,
        }
        args.update(changes)
        return mod.preview_existing_slot(config(),**args)

    def test_words_and_address(self):
        plan=self.plan()
        self.assertEqual(plan["status"],"SCHEDULE_DRY_RUN_ONLY")
        self.assertIs(plan["write_sent"],False)
        self.assertEqual(plan["register_addresses"],[0x3606,0x3607,0x3608])
        self.assertEqual(plan["existing_words"],[0x1600,0x1628,0x1046])
        self.assertEqual(plan["proposed_words"],[0x151e,0x1600,0x1132])
        self.assertEqual(plan["weekday_mask"],17)

    def test_discharge_offset(self):
        p=self.plan(direction="discharge",
            expected=mod.SlotValue("22:00","22:40",4,50))
        self.assertEqual(p["register_addresses"],[0x361B,0x361C,0x361D])

    def test_rejects_unsafe_requests(self):
        for alteration in (
            {"direction":"backup"}, {"slot_number":0}, {"slot_number":8},
            {"expected":mod.SlotValue("22:00","22:40",16,50)},
            {"days":[]},{"days":["Sat"]},{"days":["Sun"]},
            {"days":["Mon","Mon"]},{"days":["X"]},
            {"new_start":"25:00"},{"new_end":"21:00"},
            {"new_start":"22:00","new_end":"22:00"},
            {"power_percent":0},{"power_percent":101},
            {"power_percent":True},{"power_percent":75.5},
        ):
            with self.subTest(alteration=alteration):
                with self.assertRaises(mod.SchedulePreviewError):
                    self.plan(**alteration)

    def test_same_values_noop(self):
        p=self.plan(new_start="22:00",new_end="22:40",
                    days=["Fri"],power_percent=70)
        self.assertFalse(p["change_needed"])

if __name__=="__main__":
    unittest.main()
