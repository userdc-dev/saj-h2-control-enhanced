"""No-write SAJ H2 mode planning safety regression tests."""
from datetime import datetime, timedelta, timezone
import unittest
from control_core.mode_control_plan import (
    Readback, RequestedMode, UnsafeControlRequest,
    plan_mode_change, check_before_execution,
)

NOW = datetime(2026, 11, 1, 9, 0, tzinfo=timezone.utc)

def snapshot(**changes):
    source = dict(
        mode_raw=1, fallback_raw=1, charge_mask=1,
        discharge_mask=1, observed_at=NOW,
    )
    source.update(changes)
    return Readback(**source)


class TestModeControlPlan(unittest.TestCase):
    def test_planning_self_consumption_preserves_schedules(self):
        proposal = plan_mode_change(snapshot(), RequestedMode.SELF_CONSUMPTION, now=NOW)
        self.assertEqual(proposal.desired_mode_raw, 0)
        self.assertEqual(proposal.previous_mode_raw, 1)
        self.assertEqual(proposal.preserved_charge_mask, 1)
        self.assertEqual(proposal.preserved_discharge_mask, 1)
        self.assertEqual(proposal.preserved_fallback_raw, 1)
        self.assertFalse(proposal.permitted_to_write)

    def test_only_modes_zero_and_one(self):
        for invalid_mode in (2, 3, 4, -1):
            with self.assertRaises(UnsafeControlRequest):
                snapshot(mode_raw=invalid_mode)
        with self.assertRaises(UnsafeControlRequest):
            plan_mode_change(snapshot(), "backup", now=NOW)

    def test_noop_still_not_a_write(self):
        p = plan_mode_change(snapshot(), RequestedMode.TIME_OF_USE, now=NOW)
        self.assertTrue(p.request_is_noop)
        self.assertFalse(p.permitted_to_write)

    def test_fail_closed_when_fallback_not_self_consumption(self):
        with self.assertRaises(UnsafeControlRequest):
            snapshot(fallback_raw=0)

    def test_stale_snapshot_is_rejected(self):
        with self.assertRaises(UnsafeControlRequest):
            plan_mode_change(snapshot(observed_at=NOW-timedelta(seconds=181)),
                             RequestedMode.SELF_CONSUMPTION, now=NOW)

    def test_external_schedule_modification_is_detected(self):
        p = plan_mode_change(snapshot(), RequestedMode.SELF_CONSUMPTION, now=NOW)
        with self.assertRaisesRegex(UnsafeControlRequest, "Another controller"):
            check_before_execution(p, snapshot(charge_mask=2), now=NOW)

    def test_no_device_writes_even_with_matching_snapshot(self):
        p = plan_mode_change(snapshot(), RequestedMode.SELF_CONSUMPTION, now=NOW)
        with self.assertRaisesRegex(UnsafeControlRequest, "writes are disabled"):
            check_before_execution(p, snapshot(), now=NOW)


if __name__ == "__main__":
    unittest.main()
