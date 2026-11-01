"""Offline reconciliation safety tests. No device access."""
import unittest
from datetime import datetime, timedelta, timezone
from control_core.reconciliation import (
    RequestedConfiguration, DeviceObservation, State, reconcile,
)

NOW = datetime(2026, 11, 1, 8, 0, tzinfo=timezone.utc)


class TestReconciliation(unittest.TestCase):
    def test_app_requested_settings_not_yet_reflected(self):
        req = RequestedConfiguration(expected_raw=(1, 1, 0, 1, 50),
                                     submitted_at=NOW - timedelta(minutes=3))
        obs = DeviceObservation(actual_raw=(0, 1, 0, 1, 100),
                                observed_at=NOW - timedelta(seconds=5))
        r = reconcile(req, obs, now=NOW)
        self.assertEqual(r.state, State.WAITING_FOR_DEVICE)
        self.assertFalse(r.applied)

    def test_only_exact_raw_match_is_confirmed(self):
        req = RequestedConfiguration(expected_raw=(1, 1, 0, 1, 50),
                                     submitted_at=NOW - timedelta(minutes=3))
        obs = DeviceObservation(actual_raw=(1, 1, 0, 1, 50),
                                observed_at=NOW - timedelta(seconds=5))
        r = reconcile(req, obs, now=NOW)
        self.assertEqual(r.state, State.SAVED_ON_DEVICE)
        self.assertTrue(r.applied)
        self.assertIn("execution unverified", r.detail)

    def test_stale_data_cannot_confirm(self):
        req = RequestedConfiguration(expected_raw=(1, 1, 0, 1, 50),
                                     submitted_at=NOW - timedelta(minutes=9))
        obs = DeviceObservation(actual_raw=req.expected_raw,
                                observed_at=NOW - timedelta(minutes=4))
        self.assertEqual(reconcile(req, obs, now=NOW).state,
                         State.OBSERVATION_STALE)

    def test_timeout_does_not_retry(self):
        req = RequestedConfiguration(expected_raw="new",
                                     submitted_at=NOW - timedelta(minutes=11))
        obs = DeviceObservation(actual_raw="old", observed_at=NOW)
        r = reconcile(req, obs, now=NOW)
        self.assertEqual(r.state, State.UNCONFIRMED_TIMEOUT)
        self.assertFalse(r.applied)
        self.assertIn("do not retry", r.detail)

    def test_old_observation_does_not_ack(self):
        req = RequestedConfiguration(expected_raw="new",
                                     submitted_at=NOW - timedelta(seconds=10))
        obs = DeviceObservation(actual_raw="new",
                                observed_at=NOW - timedelta(seconds=20))
        self.assertNotEqual(reconcile(req, obs, now=NOW).state, State.SAVED_ON_DEVICE)

    def test_untrusted_observation_is_rejected(self):
        req = RequestedConfiguration(expected_raw="new", submitted_at=NOW)
        obs = DeviceObservation(actual_raw="new", observed_at=NOW, reliable=False)
        self.assertEqual(reconcile(req, obs, now=NOW).state, State.OBSERVATION_STALE)

    def test_unaware_timestamps_rejected(self):
        with self.assertRaises(ValueError):
            RequestedConfiguration(expected_raw="x", submitted_at=datetime(2026, 1, 1))
        with self.assertRaises(ValueError):
            reconcile(None, None, now=datetime(2026, 1, 1))

    def test_no_request_does_not_claim_application(self):
        r = reconcile(None, DeviceObservation(actual_raw="x", observed_at=NOW), now=NOW)
        self.assertEqual(r.state, State.NOT_REQUESTED)
        self.assertFalse(r.applied)


if __name__ == "__main__":
    unittest.main()
