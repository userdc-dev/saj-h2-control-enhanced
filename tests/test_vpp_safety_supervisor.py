"""Offline persistence and restart safety tests. NO Home Assistant or Modbus calls."""
from __future__ import annotations

import ast
import asyncio
import copy
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4
import unittest

ROOT=Path(__file__).resolve().parents[1]
MODULE=ROOT/"custom_components"/"saj_h2_control_enhanced"/"vpp_safety_supervisor.py"
source=MODULE.read_text()
parsed=ast.parse(source)
nodes=[node for node in parsed.body if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef))]
scope={
    "__name__":"vpp_safety_test",
    "asyncio":asyncio,"copy":copy,
    "datetime":datetime,"timedelta":timedelta,"timezone":timezone,
    "sha256":sha256,"json":json,"uuid4":uuid4,
    "Store":None,"SCHEMA":1,
    "ACTIVE":frozenset(("rehearsal_scheduled","rehearsal_running")),
    "TERMINAL":frozenset(("idle","rehearsal_completed","rehearsal_cancelled",
                          "rehearsal_interrupted","review_required")),
    "MAX_AUDIT":24,"LIVE_INVERTER_WRITES_ENABLED":False,
}
scope["STATUSES"]=scope["ACTIVE"]|scope["TERMINAL"]
exec(compile(ast.fix_missing_locations(ast.Module(body=nodes,type_ignores=[])),str(MODULE),"exec"),scope)
Supervisor=scope["VPPSafetySupervisor"]
SupervisorError=scope["SupervisorError"]
check_record=scope["check_record"]


class MemoryStore:
    def __init__(self):
        self.data=None
        self.fail_next_save=False
        self.saves=0
    async def async_load(self):
        return copy.deepcopy(self.data)
    async def async_save(self,record):
        if self.fail_next_save:
            self.fail_next_save=False
            raise OSError("storage disk full")
        self.data=copy.deepcopy(record)
        self.saves+=1


class VppSupervisorTests(unittest.TestCase):
    def setUp(self):
        self.clock=[datetime(2026,11,2,8,0,tzinfo=timezone.utc)]
        self.store=MemoryStore()
        self.entry=SimpleNamespace(entry_id="h2-control-a")
        self.charge=[0]*23
        self.discharge=[0]*21
        self.config=SimpleNamespace(mode=0,fallback=1)
        self.snap=(tuple(self.charge),tuple(self.discharge),self.config)
        self.sup=Supervisor(None,self.entry,store=self.store,
                            clock=lambda:self.clock[0])

    def advance(self,**delta):
        self.clock[0]+=timedelta(**delta)

    def preview(self,minutes=10,direction="discharge",pass_preflight=True):
        begin=self.clock[0]+timedelta(minutes=3)
        end=begin+timedelta(minutes=minutes)
        return {
            "status":"VPP_PREFLIGHT_ONLY","write_sent":False,
            "live_activation_supported":False,"can_start":False,
            "preflight_passed":pass_preflight,"duration_minutes":minutes,
            "direction":direction,"planned_start_local":begin.isoformat(),
            "planned_end_local":end.isoformat(),
            "proposed_slot":1,"requested_power_percent_raw":100,
        }

    def test_rehearsal_persists_full_original_registers_no_writes(self):
        async def run():
            await self.sup.load()
            r=await self.sup.begin_rehearsal(self.preview(),self.snap)
            self.assertEqual(r["status"],"rehearsal_scheduled")
            self.assertIs(r["write_sent"],False)
            self.assertIs(r["can_dispatch"],False)
            self.assertNotIn("baseline",r,"browser must not receive raw slot journal")
            self.assertEqual(self.store.data["baseline"]["charge_words"],self.charge)
            self.assertEqual(self.store.data["baseline"]["discharge_words"],self.discharge)
            self.assertEqual(self.store.data["baseline"]["fallback"],1)
            self.assertEqual(self.store.data["status"],"rehearsal_scheduled")
            self.advance(minutes=4)
            r=await self.sup.tick()
            self.assertEqual(r["status"],"rehearsal_running")
            self.advance(minutes=10)
            r=await self.sup.tick(snapshot=self.snap)
            self.assertEqual(r["status"],"rehearsal_completed")
            self.assertEqual(r["baseline_check"],"unchanged")
            self.assertEqual(self.store.data["status"],"rehearsal_completed")
            self.assertEqual([i["event"] for i in r["audit"]],
                             ["rehearsal_journaled","simulated_window_open",
                              "simulated_window_ended"])
        asyncio.run(run())

    def test_reload_interrupted_run_never_resumes_or_auto_restores(self):
        async def run():
            await self.sup.begin_rehearsal(self.preview(),self.snap)
            fresh=Supervisor(None,self.entry,store=self.store,
                             clock=lambda:self.clock[0])
            status=await fresh.load()
            self.assertEqual(status["status"],"rehearsal_interrupted")
            self.assertIs(status["write_sent"],False)
            self.assertEqual(status["baseline_check"],"needs_readback")
            self.assertIn("restart",status["last_error"])
            with self.assertRaisesRegex(SupervisorError,"verify"):
                await fresh.acknowledge()
            with self.assertRaises(SupervisorError):
                await fresh.begin_rehearsal(self.preview(),self.snap)
            verified=await fresh.verify_baseline(self.snap)
            self.assertEqual(verified["baseline_check"],"unchanged")
            clear=await fresh.acknowledge()
            self.assertEqual(clear["status"],"idle")
            self.assertIsNone(clear["baseline_hash"])
            self.assertEqual(clear["audit"][-1]["event"],
                             "user_acknowledged_read_only_recovery")
        asyncio.run(run())

    def test_external_schedule_change_blocks_completion_and_ack(self):
        async def run():
            await self.sup.begin_rehearsal(self.preview(),self.snap)
            self.advance(minutes=15)
            edited=list(self.charge)
            edited[5]=23
            mismatch=(tuple(edited),tuple(self.discharge),self.config)
            report=await self.sup.tick(snapshot=mismatch)
            self.assertEqual(report["status"],"review_required")
            self.assertEqual(report["baseline_check"],"changed_externally")
            with self.assertRaises(SupervisorError):
                await self.sup.acknowledge()
            report=await self.sup.verify_baseline(self.snap)
            self.assertEqual(report["baseline_check"],"unchanged")
            self.assertEqual((await self.sup.acknowledge())["status"],"idle")
        asyncio.run(run())

    def test_rehearsal_expiry_when_inverter_unreachable_is_not_success(self):
        async def run():
            await self.sup.begin_rehearsal(self.preview(minutes=5),self.snap)
            self.advance(minutes=10)
            status=await self.sup.tick(snapshot=None)
            self.assertEqual(status["status"],"review_required")
            self.assertEqual(status["baseline_check"],"not_checked")
            self.assertIsNone(status["last_verified_utc"])
        asyncio.run(run())

    def test_manual_cancel_never_sends_power_or_mode_command(self):
        async def run():
            await self.sup.begin_rehearsal(self.preview(),self.snap)
            stopped=await self.sup.cancel()
            self.assertEqual(stopped["status"],"rehearsal_cancelled")
            self.assertFalse(stopped["write_sent"])
            with self.assertRaises(SupervisorError):
                await self.sup.cancel()
        asyncio.run(run())

    def test_persist_before_transition_disk_failure(self):
        async def run():
            self.store.fail_next_save=True
            with self.assertRaises(OSError):
                await self.sup.begin_rehearsal(self.preview(),self.snap)
            self.assertEqual(self.sup.record["status"],"idle")
            self.assertIsNone(self.store.data)
            await self.sup.begin_rehearsal(self.preview(),self.snap)
            self.store.fail_next_save=True
            with self.assertRaises(OSError):
                await self.sup.cancel()
            self.assertEqual(self.sup.record["status"],"rehearsal_scheduled")
            self.assertEqual(self.store.data["status"],"rehearsal_scheduled")
        asyncio.run(run())

    def test_corrupt_or_write_claiming_journal_fails_closed(self):
        async def run():
            await self.sup.begin_rehearsal(self.preview(),self.snap)
            for mutation in (
                lambda r:r.update(write_sent=True),
                lambda r:r.update(schema=999),
                lambda r:r.update(entry_id="different-inverter"),
                lambda r:r["baseline"]["charge_words"].__setitem__(1,65535),
                lambda r:r.update(status="dispatch_active"),
            ):
                record=copy.deepcopy(self.store.data)
                mutation(record)
                self.store.data=record
                new=Supervisor(None,self.entry,store=self.store,
                               clock=lambda:self.clock[0])
                status=await new.load()
                self.assertEqual(status["status"],"review_required")
                self.assertFalse(status["can_dispatch"])
                self.assertEqual(self.store.data,record,
                                 "do not erase evidence of corrupt journal")
                with self.assertRaises(SupervisorError):
                    await new.begin_rehearsal(self.preview(),self.snap)
                self.store.data=copy.deepcopy(self.sup.record)
        asyncio.run(run())

    def test_unsafe_preview_and_unexpected_windows_refused(self):
        async def run():
            for change in (
                {"preflight_passed":False},{"write_sent":True},
                {"live_activation_supported":True},{"can_start":True},
                {"duration_minutes":6},{"direction":"curtail"},
                {"planned_end_local":self.clock[0].isoformat()},
            ):
                proposal=self.preview()
                proposal.update(change)
                with self.subTest(change=change),self.assertRaises(SupervisorError):
                    await self.sup.begin_rehearsal(proposal,self.snap)
                self.assertEqual(self.sup.record["status"],"idle")
        asyncio.run(run())

    def test_battery_soc_observation_is_read_only_and_not_journal_spam(self):
        async def run():
            await self.sup.begin_rehearsal(self.preview(),self.snap)
            initial_saves=self.store.saves
            result=await self.sup.observe_battery(soc=55.3)
            self.assertEqual(result["status"],"rehearsal_scheduled")
            self.assertEqual(result["latest_battery_soc_percent"],55.3)
            self.assertEqual(self.store.saves,initial_saves)
            self.assertFalse(result["write_sent"])
            self.assertFalse(result["can_dispatch"])
        asyncio.run(run())

    def test_missing_soc_interrupts_simulation_and_requires_verification(self):
        async def run():
            await self.sup.begin_rehearsal(self.preview(),self.snap)
            result=await self.sup.observe_battery(soc=None,error="Modbus read failed")
            self.assertEqual(result["status"],"review_required")
            self.assertEqual(result["baseline_check"],"needs_readback")
            self.assertIn("Modbus read failed",result["last_error"])
            self.assertFalse(result["write_sent"])
            self.assertEqual(self.store.data["status"],"review_required")
            with self.assertRaises(SupervisorError):
                await self.sup.acknowledge()
            await self.sup.verify_baseline(self.snap)
            self.assertEqual((await self.sup.acknowledge())["status"],"idle")
        asyncio.run(run())

    def test_soc_limits_interrupt_charge_and_discharge_simulations(self):
        async def run():
            for direction,soc in (("charge",95),("discharge",10)):
                sup=Supervisor(None,self.entry,store=MemoryStore(),
                               clock=lambda:self.clock[0])
                await sup.begin_rehearsal(
                    self.preview(direction=direction),self.snap)
                result=await sup.observe_battery(soc=soc)
                self.assertEqual(result["status"],"review_required")
                self.assertIn("breached",result["last_error"])
                self.assertFalse(result["can_dispatch"])
        asyncio.run(run())

    def test_no_dispatch_and_restoration_writes_in_module(self):
        self.assertNotIn("write_register",source)
        self.assertNotIn("write_coils",source)
        self.assertNotIn("AsyncModbusTcpClient",source)
        self.assertNotIn("asyncio.sleep",source)
        init=(MODULE.parent/"__init__.py").read_text()
        for name in ("start_vpp_safety_rehearsal","cancel_vpp_safety_rehearsal",
                     "verify_vpp_safety_baseline","vpp_rehearsal_status"):
            self.assertIn(name,init)
        self.assertNotIn('"start_vpp_dispatch"',init)
        self.assertNotIn('"stop_vpp_dispatch"',init)


if __name__=="__main__":
    unittest.main()
