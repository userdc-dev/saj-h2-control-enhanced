"""Offline fake-Modbus tests: export-source control fingerprint never writes."""
import importlib.util
from pathlib import Path
import unittest

FILE = Path(__file__).resolve().parents[1] / "scripts" / "read_only_export_source_probe.py"
spec = importlib.util.spec_from_file_location("probe", FILE)
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


class Reply:
    def __init__(self, data=None):
        self.registers = data
    def isError(self):
        return self.registers is None


def blocks():
    return {
        (0x3606, 2): [0, 1],  # test case: forgotten weekly discharge mask
        (0x3647, 1): [1],
        (0x364F, 2): [1100, 1100],
        (0x365A, 3): [1100, 0, 0],
        (0x4031, 6): [2489, 3275, 5004, 65530, 5877, 6588],
        (0x406D, 3): [0, 210, 9500],
        (0x40A0, 14): [509, 0, 0, 0, 0, 0, 2013, 0, 0, 0, 0, 0, 0, 64032],
        (0xA03D, 6): [2489, 3275, 64052, 8146, 64595, 5004],
    }


class Client:
    def __init__(self, entries=None):
        self.entries = entries if entries is not None else blocks()
        self.calls = []
    def read_holding_registers(self, *, address, count, device_id):
        self.calls.append((address, count, device_id))
        return Reply(self.entries.get((address, count)))


class OldClient(Client):
    def read_holding_registers(self, *, address, count, slave):
        self.calls.append((address, count, slave))
        return Reply(self.entries.get((address, count)))


class TestSourceFingerprint(unittest.TestCase):
    def test_known_2026_night_register_decoding_and_no_writes(self):
        c = Client()
        raw, errors = probe.take_snapshot(c)
        self.assertFalse(errors)
        r = probe.interpret(raw, errors)
        self.assertEqual(r["operating_mode_raw"], 1)
        self.assertEqual(r["discharge_mask_raw"], 1)
        self.assertEqual(r["charge_mask_raw"], 0)
        self.assertEqual(r["grid_output_percent"], 110)
        self.assertEqual(r["local_limit_power_raw"], 1100)
        self.assertEqual(r["local_anti_reflux_mode_raw"], 0)
        self.assertEqual(r["grid_voltage_v"], 248.9)
        self.assertEqual(r["house_w"], 509)
        self.assertEqual(r["battery_w"], 2013)
        self.assertEqual(r["site_grid_w"], -1504)
        self.assertEqual(r["export_w"], 1504)
        self.assertEqual(r["meter_phase_1_w"], -1484)
        self.assertEqual(r["soc_percent"], 95)
        self.assertEqual([a for a, _, _ in c.calls], [0x3606, 0x3647, 0x364F,
            0x365A, 0x4031, 0x406D, 0x40A0, 0xA03D])
    def test_legacy_slave_compatible(self):
        c = OldClient()
        raw, errors = probe.take_snapshot(c)
        self.assertFalse(errors)
        self.assertEqual(probe.interpret(raw, errors)["export_w"], 1504)
    def test_partial_missing_not_zero_or_stale(self):
        d = blocks()
        del d[(0x40A0, 14)]
        raw, errors = probe.take_snapshot(Client(d))
        r = probe.interpret(raw, errors)
        self.assertIn("energy_flows", r["errors"])
        self.assertNotIn("site_grid_w", r)
        self.assertEqual(r["meter_phase_1_w"], -1484)
    def test_soc_invalid_is_reported_not_accepted(self):
        d = blocks()
        d[(0x406D, 3)][2] = 12345
        raw, errors = probe.take_snapshot(Client(d))
        r = probe.interpret(raw, errors)
        self.assertNotIn("soc_percent", r)
        self.assertIn("battery_soc", r["errors"])
    def test_no_motor_control_ever(self):
        text = FILE.read_text()
        self.assertIn("read_holding_registers", text)
        for forbidden in ["write_register(", "write_registers(", "write_coil(",
                          "write_coils(", "subprocess.run(", "os.system("]:
            self.assertNotIn(forbidden, text)
        self.assertEqual(probe.signed16(64032), -1504)


if __name__ == "__main__":
    unittest.main()
