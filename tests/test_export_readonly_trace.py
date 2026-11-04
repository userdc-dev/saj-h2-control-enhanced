"""Offline tests for bounded FC03-only SAJ H2 export diagnosis."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

MODULE = Path(__file__).resolve().parents[1] / "scripts" / "read_only_export_trace.py"
spec = importlib.util.spec_from_file_location("read_only_export_trace", MODULE)
diag = importlib.util.module_from_spec(spec)
spec.loader.exec_module(diag)


class Response:
    def __init__(self, registers=None, error=False):
        self.registers = registers
        self.error = error

    def isError(self):
        return self.error


def example_blocks():
    # Real owner-provided 2026-11-04 14:09 Adelaide meter capture,
    # combined with 14:04 illustrative flow block (NOT same-time physical
    # measurements). Tests validate decoding, NOT simultaneous physics.
    meter = [
        2489, 3275, 57864, 8146, 64595, 5004,
        0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    ]
    return {
        (0x3647, 1): [0],
        (0x365A, 3): [1100, 0, 0],
        (0x406D, 3): [0, 290, 10000],
        (0x40A0, 14): [
            943, 0, 0, 0, 0, 6277, 13, 5848,
            6599, 5821, 6602, 0, 53, 57864,
        ],
        (0xA03D, 18): meter,
    }


class ReadOnlyClient:
    def __init__(self, blocks=None):
        self.blocks = blocks if blocks is not None else example_blocks()
        self.reads = []

    def read_holding_registers(self, *, address, count, device_id):
        self.reads.append((address, count, device_id))
        value = self.blocks.get((address, count))
        if value is None:
            return Response(error=True)
        return Response(value)


class LegacyReadOnlyClient(ReadOnlyClient):
    def read_holding_registers(self, *, address, count, slave):
        self.reads.append((address, count, slave))
        value = self.blocks.get((address, count))
        return Response(value, error=value is None)


class ExportReadOnlyTests(unittest.TestCase):
    def test_signed_grid_equals_meter_a_owner_capture(self):
        client = ReadOnlyClient()
        snapshot = diag.take_snapshot(
            client, unit_id=1, timestamp="2026-11-04T14:09:38+10:30")
        self.assertEqual(snapshot["site_grid_w"], -7672)
        self.assertEqual(snapshot["export_w"], 7672)
        self.assertEqual(snapshot["meter_grid_w"], -7672)
        self.assertEqual(snapshot["meter_difference_w"], 0)
        self.assertEqual(snapshot["solar_w"], 6277)
        self.assertEqual(snapshot["house_w"], 943)
        self.assertEqual(snapshot["battery_aggregate_w"], 13)
        self.assertEqual(snapshot["soc_percent"], 100)
        self.assertEqual(snapshot["battery_temp_c"], 29)
        self.assertEqual(snapshot["mode_raw"], 0)
        self.assertEqual(snapshot["anti_reflux_mode_raw"], 0)
        self.assertEqual(snapshot["anti_reflux_power_raw"], 1100)
        self.assertEqual(len(client.reads), 5)

    def test_legacy_slave_kw_supported_without_modbus_writes(self):
        client = LegacyReadOnlyClient()
        snapshot = diag.take_snapshot(client)
        self.assertEqual(snapshot["export_w"], 7672)
        self.assertEqual(client.reads[0], (0x3647, 1, 1))
        self.assertEqual([x[0] for x in client.reads],
                         [0x3647, 0x365A, 0x406D, 0x40A0, 0xA03D])

    def test_positive_grid_power_is_import_not_export(self):
        blocks = example_blocks()
        blocks[(0x40A0, 14)][13] = 1500
        blocks[(0xA03D, 18)][2] = 1500
        snapshot = diag.take_snapshot(ReadOnlyClient(blocks))
        self.assertEqual(snapshot["site_grid_w"], 1500)
        self.assertEqual(snapshot["export_w"], 0)
        self.assertEqual(snapshot["meter_grid_w"], 1500)

    def test_failed_reads_are_unknown_never_fabricated_zero(self):
        blocks = example_blocks()
        del blocks[(0xA03D, 18)]
        snapshot = diag.take_snapshot(ReadOnlyClient(blocks))
        self.assertIsNone(snapshot["meter_grid_w"])
        self.assertIsNone(snapshot["meter_difference_w"])
        self.assertIn("meter_a", snapshot["errors"])
        self.assertIn("mismatch/unavailable", diag.format_snapshot(snapshot))
        del blocks[(0x40A0, 14)]
        snapshot = diag.take_snapshot(ReadOnlyClient(blocks))
        self.assertIsNone(snapshot["site_grid_w"])
        self.assertIsNone(snapshot["export_w"])
        self.assertIn("No verified export", diag.summarize([snapshot]))

    def test_invalid_soc_fails_closed_without_stale_state(self):
        blocks = example_blocks()
        blocks[(0x406D, 3)][2] = 12000
        snapshot = diag.take_snapshot(ReadOnlyClient(blocks))
        self.assertIsNone(snapshot["soc_percent"])
        self.assertIsNone(snapshot["battery_temp_c"])
        self.assertIn("battery", snapshot["errors"])
        self.assertEqual(snapshot["export_w"], 7672)

    def test_repeated_samples_bounded_and_no_sleep_after_last(self):
        client = ReadOnlyClient()
        waits = []
        with patch("builtins.print"):
            records = diag.run_trace(client, samples=3, interval=10,
                                     sleep=lambda x: waits.append(x))
        self.assertEqual(len(records), 3)
        self.assertEqual(waits, [10, 10])
        self.assertEqual(len(client.reads), 15)
        for bad in (0, 13, True, 20):
            with self.assertRaises(ValueError):
                diag.run_trace(client, samples=bad, interval=20)
        for bad in (0, 2, 121):
            with self.assertRaises(ValueError):
                diag.run_trace(client, samples=1, interval=bad)

    def test_one_snapshot_does_not_claim_a_network_limit(self):
        snapshot = diag.take_snapshot(ReadOnlyClient())
        summary = diag.summarize([snapshot])
        self.assertIn("does NOT reveal an approved SAPN limit", summary)
        self.assertNotIn("actual export limit:", summary)
        self.assertEqual(diag.signed16(0xFFFF), -1)
        self.assertEqual(diag.signed16(0x8000), -32768)
        with self.assertRaises(ValueError):
            diag.signed16(65536)

    def test_script_has_no_write_or_automatic_battery_control(self):
        source = MODULE.read_text()
        for forbidden in (
            "write_register(", "write_registers(", "write_coil(",
            "write_coils(", "start_vpp_dispatch", "stop_vpp_dispatch",
            "subprocess.", "os.system(", "0x365C =",
        ):
            self.assertNotIn(forbidden, source)
        self.assertIn("READ_BLOCKS =", source)
        self.assertIn("read_holding_registers", source)


if __name__ == "__main__":
    unittest.main()
