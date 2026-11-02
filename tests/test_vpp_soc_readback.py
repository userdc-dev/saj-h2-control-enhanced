"""VPP preflight battery SOC must come from fresh verified Modbus reads.

Never infer safety from a hard-coded or stale Home Assistant sensor ID.
The test module imports only standard-library dependencies and makes no writes.
"""
import asyncio
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest

ROOT=Path(__file__).resolve().parents[1]
COMP=ROOT/"custom_components"/"saj_h2_control_enhanced"
PATH=COMP/"vpp_soc_readback.py"
spec=importlib.util.spec_from_file_location("vpp_soc_readback",PATH)
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class Reply:
    def __init__(self, registers, error=False):
        self.registers=registers
        self._error=error
    def isError(self):
        return self._error


class NewModbusClient:
    def __init__(self, replies):
        self.replies=list(replies)
        self.requests=[]
    async def read_holding_registers(self, address, count, device_id):
        self.requests.append((address,count,device_id))
        item=self.replies.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class OldModbusClient(NewModbusClient):
    async def read_holding_registers(self, address, count, slave):
        self.requests.append((address,count,slave))
        item=self.replies.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class VPPSocReadbackTests(unittest.TestCase):
    def read(self, client):
        return asyncio.run(module.read_verified_battery_soc(client,unit_id=1))

    def test_new_pymodbus_fresh_double_read_and_scale(self):
        for raw, expected in ((4300,43.0),(9876,98.76),(10000,100.0),
                              (0,0.0)):
            with self.subTest(raw=raw):
                client=NewModbusClient([Reply([raw]),Reply([raw])])
                self.assertEqual(self.read(client),expected)
                self.assertEqual(client.requests,[(0x406F,1,1),(0x406F,1,1)])
        client=NewModbusClient([Reply([5010]),Reply([5040])])
        self.assertEqual(self.read(client),50.4,
                         "latest verified sample, not an average or cached value")

    def test_older_pymodbus_slave_keyword(self):
        client=OldModbusClient([Reply([4300]),Reply([4300])])
        self.assertEqual(self.read(client),43.0)
        self.assertEqual(client.requests,[(0x406F,1,1),(0x406F,1,1)])

    def test_rejects_missing_faulty_and_out_of_bounds_values(self):
        examples=[
            [None,Reply([4300])],
            [Reply([4300],error=True),Reply([4300])],
            [Reply([]),Reply([4300])],
            [Reply([4300,4300]),Reply([4300])],
            [Reply([65535]),Reply([65535])],
            [Reply([10001]),Reply([10001])],
            [Reply([-1]),Reply([-1])],
            [Reply([50.5]),Reply([50.5])],
            [Reply([True]),Reply([True])],
            [Reply([4300]),Reply([65535])],
            [Reply([4300]),Reply([4500])],
            [OSError("timeout"),Reply([4300])],
        ]
        for replies in examples:
            with self.subTest(replies=replies):
                client=NewModbusClient(replies)
                with self.assertRaises(module.BatterySocReadbackError):
                    self.read(client)
                self.assertFalse(hasattr(client,"write_registers"))

    def test_integrates_with_vpp_preflight_without_hardcoded_entity(self):
        entry=(COMP/"__init__.py").read_text()
        preflight=entry.split("    async def _fresh_vpp_preflight(data):",1)[1]
        preflight=preflight.split("    async def preview_vpp_dispatch(call):",1)[0]
        self.assertIn("soc=await read_verified_battery_soc(client,unit_id=UNIT_ID)",
                      preflight)
        self.assertIn("snapshot=await read_full(client)",preflight)
        self.assertNotIn("hass.states.get(",preflight)
        self.assertNotIn("last_updated",preflight)
        self.assertIn("soc=soc",preflight)
        self.assertIn("BatterySocReadbackError",preflight)
        self.assertIn("soc_readback_error",preflight)
        self.assertNotIn("write_register",preflight)
        self.assertNotIn("write_coil",preflight)
        module_source=PATH.read_text()
        self.assertNotIn("write_register(",module_source)
        self.assertNotIn("write_coil(",module_source)
        # The SOC bounds in the pre-existing planner must not be weakened.
        planner=(COMP/"vpp_quick_preview.py").read_text()
        self.assertIn('soc >= 95',planner)
        self.assertIn('soc <= 10',planner)


if __name__=="__main__":
    unittest.main()
