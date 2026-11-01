"""Offline tests: python -m unittest discover -s tests -p 'test_*.py'."""
import unittest
from datetime import datetime, timedelta, timezone
from control_core.telemetry import ENTITY_IDS, Observation, parse_snapshot, display_diagnostics
from control_core.planner import review_action

NOW = datetime(2026, 11, 1, 6, tzinfo=timezone.utc)
def healthy():
    data = {
        "soc_pct": ("42", "%"),
        "battery_w": ("-347", "W"),
        "battery_activity": ("Charging", None),
        "mode": ("Self-consumption", None),
        "solar_w": ("975", "W"),
        "home_w": ("628", "W"),
        "grid_w": ("0", "W"),
        "stored_kwh": ("16.8", "kWh"),
        "battery_temp_c": ("21", "°C"),
        "battery_voltage_v": ("420", "V"),
    }
    return {ENTITY_IDS[k]: Observation(*v) for k, v in data.items()}

class TelemetryTests(unittest.TestCase):
    def test_missing_heartbeat_fails_closed(self):
        result = parse_snapshot(healthy(), now=NOW)
        self.assertIsNone(result.snapshot)
        self.assertIn("no verified successful-poll heartbeat", result.problems)

    def test_good_sample_still_never_enables_writes(self):
        result = parse_snapshot(healthy(), now=NOW, verified_last_poll=NOW-timedelta(seconds=10))
        self.assertIsNotNone(result.snapshot)
        self.assertFalse(result.ready_for_writes)
        self.assertFalse(display_diagnostics(result)["control_enabled"])

    def test_stale_poll_fails_closed(self):
        result = parse_snapshot(healthy(), now=NOW, verified_last_poll=NOW-timedelta(minutes=2))
        self.assertIsNone(result.snapshot)

    def test_no_fake_zeros(self):
        states = healthy()
        del states[ENTITY_IDS["home_w"]]
        result = parse_snapshot(states, now=NOW, verified_last_poll=NOW)
        self.assertIsNone(result.snapshot)

    def test_mode_restrictions(self):
        states = healthy()
        states[ENTITY_IDS["mode"]] = Observation("Backup (avoid)")
        result = parse_snapshot(states, now=NOW, verified_last_poll=NOW)
        self.assertIsNone(result.snapshot)
        self.assertTrue(any("mode" in r for r in result.problems))

    def test_conflicting_units(self):
        states = healthy()
        states[ENTITY_IDS["battery_w"]] = Observation("0.347", "kW")
        result = parse_snapshot(states, now=NOW, verified_last_poll=NOW)
        self.assertIsNone(result.snapshot)

    def test_request_is_always_non_executable(self):
        result = parse_snapshot(healthy(), now=NOW, verified_last_poll=NOW)
        for direction in ("charge", "discharge"):
            review = review_action(direction, 15, None, result)
            self.assertFalse(review.allowed_to_execute)
            self.assertIsNotNone(review.proposal)

    def test_invalid_duration(self):
        result = parse_snapshot(healthy(), now=NOW, verified_last_poll=NOW)
        self.assertIsNone(review_action("charge", True, None, result).proposal)
        self.assertIsNone(review_action("charge", 999, None, result).proposal)

if __name__ == "__main__":
    unittest.main()
