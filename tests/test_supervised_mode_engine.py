"""Offline checks: the real-mode backend must NEVER write in this release."""
import asyncio
import unittest

from control_core.supervised_mode_engine import (
    LIVE_WRITE_ENABLED, MODE_REGISTER, ModeError, read_snapshot,
    supervised_mode_change,
)


class FakeModbus:
    def __init__(self):
        self.calls = []
        self.values = {0x3604: 1, 0x3605: 1, 0x3647: 0, 0x365F: 1}

    async def read_holding(self, address, count):
        self.calls.append(("read", address, count))
        return tuple(self.values[address + i] for i in range(count))

    async def write_single(self, address, value):
        self.calls.append(("WRITE", address, value))
        self.values[address] = value
        return True


class ModeEngineTests(unittest.TestCase):
    def test_profile_and_confirmed_target_still_cannot_write(self):
        async def run():
            fake = FakeModbus()
            with self.assertRaisesRegex(ModeError, "writes disabled"):
                await supervised_mode_change(
                    fake, 1, confirm="CHANGE_MODE_TO_1",
                    profile_model="H2-10K-S3-A",
                    profile_control_firmware="v2.018",
                )
            self.assertFalse(any(c[0] == "WRITE" for c in fake.calls))
        self.assertFalse(LIVE_WRITE_ENABLED)
        asyncio.run(run())

    def test_modes_2_and_3_never_accepted(self):
        async def run():
            for mode in (2, 3, 4, -1, True):
                fake = FakeModbus()
                with self.assertRaises(ModeError):
                    await supervised_mode_change(
                        fake, mode, confirm=f"CHANGE_MODE_TO_{mode}",
                        profile_model="H2-10K-S3-A",
                        profile_control_firmware="v2.018",
                    )
                self.assertEqual(fake.calls, [])
        asyncio.run(run())

    def test_wrong_hardware_and_missing_confirmation_blocked(self):
        async def run():
            for model, firmware, confirm in [
                ("H2-10K-S3", "v2.018", "CHANGE_MODE_TO_1"),
                ("H2-10K-S3-A", "v9.999", "CHANGE_MODE_TO_1"),
                ("H2-10K-S3-A", "v2.018", "yes"),
            ]:
                fake = FakeModbus()
                with self.assertRaises(ModeError):
                    await supervised_mode_change(
                        fake, 1, confirm=confirm, profile_model=model,
                        profile_control_firmware=firmware)
                self.assertEqual(fake.calls, [])
        asyncio.run(run())

    def test_stable_readback_checks_mode_fallback_and_masks(self):
        async def run():
            fake = FakeModbus()
            s = await read_snapshot(fake)
            self.assertEqual((s.mode, s.fallback, s.charge_mask, s.discharge_mask),
                             (0, 1, 1, 1))
            self.assertEqual(len(fake.calls), 6)
            fake.values[0x365F] = 0
            with self.assertRaisesRegex(ModeError, "fallback"):
                await read_snapshot(fake)
            fake.values[0x365F] = 1
            fake.values[0x3647] = 2
            with self.assertRaisesRegex(ModeError, "Unsupported"):
                await read_snapshot(fake)
        asyncio.run(run())


if __name__ == "__main__":
    unittest.main()
