"""Offline integration tests with a fake Modbus inverter: NO network, NO hardware."""
import asyncio
import importlib.util
from pathlib import Path
import sys
import types
import unittest

ROOT = Path("custom_components/saj_h2_control_enhanced")
PACKAGE = "test_saj_full"

package = types.ModuleType(PACKAGE)
package.__path__ = [str(ROOT)]
sys.modules[PACKAGE] = package
pymodbus = types.ModuleType("pymodbus")
client_module = types.ModuleType("pymodbus.client")
client_module.AsyncModbusTcpClient = lambda *a,**k: None
pymodbus.client = client_module
sys.modules.setdefault("pymodbus", pymodbus)
sys.modules.setdefault("pymodbus.client", client_module)

def load(name):
    spec=importlib.util.spec_from_file_location(PACKAGE+"."+name, ROOT/(name+".py"))
    module=importlib.util.module_from_spec(spec)
    sys.modules[spec.name]=module
    spec.loader.exec_module(module)
    return module

load("const")
protocol=load("tou_protocol")
engine=load("schedule_transaction")


class Reply:
    def __init__(self, values, error=False):
        self.registers=values
        self.error=error
    def isError(self):
        return self.error

class FakeModbus:
    def __init__(self, *,mode=0, fail_at=None):
        self.registers = {0x3647:mode,0x365f:1}
        charge=[1,1,5632,5672,4166]+[0]*18
        discharge=[5632,5672,1074]+[0]*18
        for i,v in enumerate(charge):self.registers[0x3604+i]=v
        for i,v in enumerate(discharge):self.registers[0x361b+i]=v
        self.writes=[]
        self.fail_at=fail_at
        self.connected=False
    async def connect(self):
        self.connected=True;return True
    def close(self):
        self.connected=False
    async def read_holding_registers(self,address,count,device_id=1):
        return Reply([self.registers[address+i] for i in range(count)])
    async def write_register(self,address,value,device_id=1):
        self.writes.append((address,value))
        if self.fail_at==len(self.writes):
            return Reply([],error=True)
        self.registers[address]=value
        return Reply([])

async def no_wait(_):
    return None

BASE_CHARGE=[{"slot":1,"start":"22:00","end":"22:40",
              "day_mask":16,"percent":70}]
BASE_DISCHARGE=[{"slot":1,"start":"22:00","end":"22:40",
                 "day_mask":4,"percent":50}]

def propose(rows):
    return [
        {"slot":r["slot"],"start":r["start"],"end":r["end"],
         "days":[name for name,bit in engine.BITS.items() if r["day_mask"]&bit],
         "percent":r["percent"]}
        for r in rows
    ]

def inputs():
    return dict(
        expected_charge=BASE_CHARGE,expected_discharge=BASE_DISCHARGE,
        proposed_charge=propose(BASE_CHARGE),
        proposed_discharge=propose(BASE_DISCHARGE),
    )

class FullScheduleTests(unittest.TestCase):
    def test_single_time_edit_is_two_verified_writes(self):
        async def run():
            fake=FakeModbus()
            data=inputs()
            data["proposed_charge"][0].update(start="21:30",end="22:00")
            result=await engine.execute_plan(
                host="127.0.0.1",port=502,
                confirmation=engine.CONFIRM_PHRASE,
                device_model="H2-10K-S3-A",control_firmware="v2.018",
                transport=lambda *a,**k:fake,sleep=no_wait,**data)
            self.assertEqual(result["status"],"SCHEDULE_VERIFIED_BY_MODBUS")
            self.assertEqual(fake.writes,[(0x3606,0x151e),(0x3607,0x1600)])
            self.assertEqual(fake.registers[0x3608],0x1046)
            self.assertEqual(fake.registers[0x361b],0x1600)
        asyncio.run(run())

    def test_add_edit_and_remove_cover_both_directions_and_masks_last(self):
        async def run():
            fake=FakeModbus()
            data=inputs()
            data["proposed_charge"]=[
                {"slot":2,"start":"08:00","end":"08:30",
                 "days":["Mon","Tue"],"percent":50}
            ]
            data["proposed_discharge"]=[
                {"slot":1,"start":"21:00","end":"21:30",
                 "days":["Wed"],"percent":50},
                {"slot":7,"start":"12:00","end":"13:00",
                 "days":["Fri"],"percent":70}
            ]
            result=await engine.execute_plan(
                host="127.0.0.1",port=502,
                confirmation=engine.CONFIRM_PHRASE,
                device_model="H2-10K-S3-A",control_firmware="v2.018",
                transport=lambda *a,**k:fake,sleep=no_wait,**data)
            self.assertEqual(result["status"],"SCHEDULE_VERIFIED_BY_MODBUS")
            self.assertEqual(fake.writes[-2:],[(0x3604,2),(0x3605,65)])
            self.assertEqual(fake.registers[0x3604:0x3605] if False else fake.registers[0x3604],2)
            self.assertEqual(fake.registers[0x3605],65)
            self.assertEqual(fake.registers[0x3609],0x0800)
            self.assertEqual(fake.registers[0x361b+18],0x0c00)
        asyncio.run(run())

    def test_later_window_extends_end_before_start(self):
        async def run():
            fake=FakeModbus()
            data=inputs()
            data["proposed_charge"][0].update(start="23:30",end="23:50")
            result=await engine.execute_plan(
                host="127.0.0.1",port=502,
                confirmation=engine.CONFIRM_PHRASE,
                device_model="H2-10K-S3-A",control_firmware="v2.018",
                transport=lambda *a,**k:fake,sleep=no_wait,**data)
            self.assertEqual(result["status"],"SCHEDULE_VERIFIED_BY_MODBUS")
            self.assertEqual(fake.writes,[
                (0x3607,0x1732),  # extend end before start crosses old end
                (0x3606,0x171e)
            ])
        asyncio.run(run())

    def test_weekend_bit_roundtrip(self):
        async def run():
            fake=FakeModbus()
            data=inputs()
            data["proposed_charge"][0]["days"]=["Sat","Sun"]
            plan=engine.build_plan(await engine.read_full(fake),**data)
            self.assertIn(0x6046, [step.value for step in plan.steps])
        asyncio.run(run())

    def test_tou_mode_paused_and_restored_after_verified_schedule_writes(self):
        async def run():
            fake=FakeModbus(mode=1)
            data=inputs()
            data["proposed_charge"][0].update(start="21:30",end="22:00")
            result=await engine.execute_plan(
                host="127.0.0.1",port=502,
                confirmation=engine.CONFIRM_PHRASE,
                device_model="H2-10K-S3-A",control_firmware="v2.018",
                transport=lambda *a,**k:fake,sleep=no_wait,**data)
            self.assertEqual(result["status"],"SCHEDULE_VERIFIED_BY_MODBUS")
            self.assertEqual(fake.writes,[
                (0x3647,0),(0x3606,0x151e),(0x3607,0x1600),(0x3647,1)
            ])
            self.assertEqual(fake.registers[0x3647],1)
        asyncio.run(run())

    def test_plan_noop(self):
        async def run():
            fake=FakeModbus()
            snap=await engine.read_full(fake)
            result=engine.build_plan(snap,**inputs())
            self.assertEqual(result.changes,0)
            self.assertEqual(result.steps,())
        asyncio.run(run())

    def test_fail_closed_stale_and_invalid(self):
        async def run():
            fake=FakeModbus()
            original=await engine.read_full(fake)
            invalids=[
                {"expected_charge":[]},
                {"proposed_charge":[dict(propose(BASE_CHARGE)[0],days=["Mon","Mon"])]},
                {"proposed_charge":[dict(propose(BASE_CHARGE)[0],start="23:00",end="01:00")]},
                {"proposed_charge":[dict(propose(BASE_CHARGE)[0],percent=0)]},
                {"proposed_charge":[dict(propose(BASE_CHARGE)[0],percent=True)]},
                {"proposed_charge":[dict(propose(BASE_CHARGE)[0],start="21:00",end="21:00")]},
                {"proposed_charge":[dict(propose(BASE_CHARGE)[0],slot=8)]},
                {"proposed_charge":[dict(propose(BASE_CHARGE)[0])]*2},
            ]
            for change in invalids:
                with self.subTest(change=change):
                    with self.assertRaises(engine.ScheduleTransactionError):
                        engine.build_plan(original,**{**inputs(),**change})
            fake.registers[0x3647]=1
            live=await engine.read_full(fake)
            self.assertEqual(live[2].mode,1)
            self.assertEqual(engine.build_plan(live,**inputs()).changes,0)
            self.assertEqual(fake.writes,[])
        asyncio.run(run())

    def test_partial_write_failure_no_retry(self):
        async def run():
            fake=FakeModbus(fail_at=2)
            data=inputs()
            data["proposed_charge"][0].update(start="21:30",end="22:00")
            with self.assertRaises(engine.ScheduleTransactionError):
                await engine.execute_plan(
                    host="127.0.0.1",port=502,
                    confirmation=engine.CONFIRM_PHRASE,
                    device_model="H2-10K-S3-A",control_firmware="v2.018",
                    transport=lambda *a,**k:fake,sleep=no_wait,**data)
            self.assertEqual(fake.writes,[(0x3606,0x151e),(0x3607,0x1600)])
            self.assertEqual(fake.registers[0x3606],0x151e)
            self.assertEqual(fake.registers[0x3607],0x1628)
        asyncio.run(run())

if __name__=="__main__":
    unittest.main()
