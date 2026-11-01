"""Full fake-Modbus tests; absolutely no real inverter I/O."""
import asyncio
import importlib.util
from pathlib import Path
import sys
import types
import unittest

ROOT = Path("custom_components/saj_h2_control_enhanced")
PACKAGE = "test_saj_fallback"

pkg = types.ModuleType(PACKAGE)
pkg.__path__ = [str(ROOT)]
sys.modules[PACKAGE] = pkg
pymodbus = types.ModuleType("pymodbus")
client_mod = types.ModuleType("pymodbus.client")
client_mod.AsyncModbusTcpClient = lambda *args, **kwargs: None
pymodbus.client = client_mod
sys.modules.setdefault("pymodbus", pymodbus)
sys.modules.setdefault("pymodbus.client", client_mod)


def load(name):
    spec = importlib.util.spec_from_file_location(PACKAGE + "." + name, ROOT / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


load("const")
load("tou_protocol")
engine = load("supervised_fallback")


class Reply:
    def __init__(self, registers, error=False):
        self.registers = registers
        self.error = error
    def isError(self):
        return self.error


class Inverter:
    def __init__(self, mode=1, fallback=1, fail_ack=False, alter_mode=False):
        self.regs = {0x3647: mode, 0x365F: fallback}
        charge = [1,1,0x1600,0x1628,0x1046] + [0]*18
        discharge = [0x1600,0x1628,0x0432] + [0]*18
        for i, value in enumerate(charge):
            self.regs[0x3604+i] = value
        for i, value in enumerate(discharge):
            self.regs[0x361B+i] = value
        self.writes = []
        self.fail_ack = fail_ack
        self.alter_mode = alter_mode
    async def connect(self):
        return True
    async def read_holding_registers(self, address, count, device_id=1):
        return Reply([self.regs[address+i] for i in range(count)])
    async def write_register(self, address, value, device_id=1):
        self.writes.append((address, value))
        if self.fail_ack:
            return Reply([], True)
        self.regs[address] = value
        if self.alter_mode:
            self.regs[0x3647] = 0
        return Reply([])
    def close(self):
        pass


async def fast_sleep(_):
    pass


def args(device, target=0, before=1, mode=1, confirmation=None):
    return dict(
        host="172.16.1.4",port=502,target=target,
        expected_fallback=before,expected_mode=mode,
        standby_confirmation=confirmation,device_model="H2-10K-S3-A",
        control_firmware="v2.018",
        client_factory=lambda *a, **kw: device,sleep=fast_sleep,
    )


class FallbackTests(unittest.TestCase):
    def test_confirmed_standby_write_is_one_register_only(self):
        async def check():
            device = Inverter()
            result = await engine.run_fallback_control(
                **args(device,confirmation=engine._STANDBY_CONFIRM))
            self.assertEqual(result["status"], "FALLBACK_VERIFIED_BY_MODBUS")
            self.assertEqual(device.writes, [(0x365F, 0)])
            self.assertEqual(result["after_fallback_raw"], 0)
            self.assertEqual(device.regs[0x3647], 1)
            self.assertEqual(device.regs[0x3608], 0x1046)
        asyncio.run(check())

    def test_restore_self_consumption_without_standby_phrase(self):
        async def check():
            device = Inverter(mode=0, fallback=0)
            result = await engine.run_fallback_control(
                **args(device,target=1,before=0,mode=0))
            self.assertEqual(result["status"], "FALLBACK_VERIFIED_BY_MODBUS")
            self.assertEqual(device.writes, [(0x365F, 1)])
        asyncio.run(check())

    def test_missing_confirmation_stale_mode_and_wrong_profile_write_nothing(self):
        async def check():
            cases = [
                args(Inverter()),  # no standby authorization
                args(Inverter(mode=0),confirmation=engine._STANDBY_CONFIRM),
                {**args(Inverter(),confirmation=engine._STANDBY_CONFIRM),
                 "device_model": "H2-8K-S3-A"},
                {**args(Inverter(),confirmation=engine._STANDBY_CONFIRM),
                 "target":2},
            ]
            for values in cases:
                client = values["client_factory"]("unused")
                with self.subTest(values=values):
                    with self.assertRaises(engine.FallbackWriteError):
                        await engine.run_fallback_control(**values)
                    self.assertEqual(client.writes, [])
        asyncio.run(check())

    def test_unsupported_mode_is_fail_closed(self):
        async def check():
            device = Inverter(mode=2)
            with self.assertRaisesRegex(engine.FallbackWriteError,"Unsupported operating mode"):
                await engine.run_fallback_control(
                    **args(device,confirmation=engine._STANDBY_CONFIRM))
            self.assertEqual(device.writes, [])
        asyncio.run(check())

    def test_lost_ack_leaves_uncertain_single_write_no_retry(self):
        async def check():
            device = Inverter(fail_ack=True)
            with self.assertRaisesRegex(engine.FallbackWriteError,"acknowledgement"):
                await engine.run_fallback_control(
                    **args(device,confirmation=engine._STANDBY_CONFIRM))
            self.assertEqual(device.writes, [(0x365F,0)])
        asyncio.run(check())

    def test_competing_controller_detected_after_write(self):
        async def check():
            device = Inverter(alter_mode=True)
            with self.assertRaisesRegex(engine.FallbackWriteError,"Mode or schedules changed"):
                await engine.run_fallback_control(
                    **args(device,confirmation=engine._STANDBY_CONFIRM))
            self.assertEqual(device.writes, [(0x365F,0)])
        asyncio.run(check())


if __name__ == "__main__":
    unittest.main()
