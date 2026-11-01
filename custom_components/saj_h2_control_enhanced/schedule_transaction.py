"""SAJ H2 complete TOU editor: plan / compare / guarded sequential writes.

Charge and discharge each support up to seven slot indices. A plan can edit,
add, or disable individual slots. This backend is explicit-action only; no
polling, auto-apply, background write, or auto-rollback.

SAFETY:
* Editing is allowed ONLY in Self-consumption mode (0), outside TOU (1).
* Full double read before planning, exact frontend baseline for BOTH groups.
* Only differing slot words written; slot enable masks updated LAST.
* Function 06 single-register writes, verification after each write.
* On ambiguous ACK, mismatch, lost connection, or app/VPP conflict: STOP.
  Partial states are possible; the user must inspect eLEKeeper before retry.
* Sat and Sun individually are NOT yet verified on this inverter. The paired
  Sat+Sun mask 96 is supported for previews and may be enabled with a
  separate weekend-verified opt-in in the future, but not live yet.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
import inspect
import logging
import re

from pymodbus.client import AsyncModbusTcpClient
from .const import UNIT_ID
from .tou_protocol import (
    CHARGE_START, CHARGE_COUNT, DISCHARGE_START, DISCHARGE_COUNT,
    MODE_ADDR, FALLBACK_ADDR, decode_config,
)

_LOGGER = logging.getLogger(__name__)
CONFIRM_PHRASE = "I AUTHORIZE TOU SCHEDULE CHANGES"
BITS = {"Mon":1, "Tue":2, "Wed":4, "Thu":8, "Fri":16, "Sat":32, "Sun":64}
MAX_WRITES_PER_ACTION = 44
BASE_CHARGE, BASE_DISCHARGE = 0x3606, 0x361B


class ScheduleTransactionError(RuntimeError):
    pass


def clock(value):
    if type(value) is not str or not re.fullmatch(
        r"(?:[01][0-9]|2[0-3]):[0-5][0-9]", value
    ):
        raise ScheduleTransactionError("Time must be HH:MM (00:00–23:59)")
    h,m = (int(i) for i in value.split(":"))
    return (h << 8) | m


def parse_days(days):
    if type(days) is not list or not days or len(days) != len(set(days)):
        raise ScheduleTransactionError("Choose unique weekdays for each slot")
    if any(type(x) is not str or x not in BITS for x in days):
        raise ScheduleTransactionError(
            "Invalid weekday. Choose Monday–Sunday"
        )
    return sum(BITS[x] for x in days)


def active_rows(config, direction):
    slots = config.charge_slots if direction == "charge" else config.discharge_slots
    return [
        {"slot":s.number, "start":s.start, "end":s.end,
         "day_mask":s.day_mask, "percent":s.power_percent}
        for s in slots if s.enabled
    ]


def validate_snapshot(snap):
    charge, discharge, config = snap
    if config.mode not in (0,1):
        raise ScheduleTransactionError(
            "Schedule editing is allowed only in Self-consumption or Time-of-Use mode"
        )
    if config.fallback != 1:
        raise ScheduleTransactionError("Outside-TOU fallback must be Self-consumption")
    if config.charge_mask > 127 or config.discharge_mask > 127:
        raise ScheduleTransactionError("Invalid enabled-slot masks")
    for direction in ("charge","discharge"):
        for s in (config.charge_slots if direction=="charge" else config.discharge_slots):
            if not s.enabled:
                continue
            if not (0 <= s.day_mask <= 127 and 1 <= s.power_percent <= 100):
                raise ScheduleTransactionError("Invalid existing active slot")
            if s.start == "unknown" or s.end == "unknown":
                raise ScheduleTransactionError("Invalid existing slot times")
    return snap


def _expected_rows(rows):
    if type(rows) is not list or len(rows)>7:
        raise ScheduleTransactionError("Expected baseline must contain <=7 slots")
    result=[]
    used=set()
    for r in rows:
        if type(r) is not dict:
            raise ScheduleTransactionError("Invalid original slot")
        n=r.get("slot")
        if type(n) is not int or not 1 <= n <= 7 or n in used:
            raise ScheduleTransactionError("Invalid or repeated baseline slot")
        used.add(n)
        start,end=r.get("start"),r.get("end")
        clock(start);clock(end)
        mask,power=r.get("day_mask"),r.get("percent")
        if type(mask) is not int or not 0 <= mask <= 127:
            raise ScheduleTransactionError("Invalid expected weekday mask")
        if type(power) is not int or not 0 <= power <= 100:
            raise ScheduleTransactionError("Invalid expected power")
        result.append({"slot":n,"start":start,"end":end,
                       "day_mask":mask,"percent":power})
    return sorted(result,key=lambda x:x["slot"])


def _desired_rows(rows):
    if type(rows) is not list or len(rows)>7:
        raise ScheduleTransactionError("Maximum seven periods in each direction")
    result=[]
    used=set()
    for r in rows:
        if type(r) is not dict:
            raise ScheduleTransactionError("Invalid proposed slot")
        n=r.get("slot")
        if type(n) is not int or not 1 <= n <=7 or n in used:
            raise ScheduleTransactionError("Invalid/duplicate slot number")
        used.add(n)
        start,end=r.get("start"),r.get("end")
        clock(start);clock(end)
        if start>=end:
            raise ScheduleTransactionError(
                "Start must be before end; overnight windows unverified")
        mask=parse_days(r.get("days"))
        power=r.get("percent")
        if type(power) is not int or not 1<=power<=100:
            raise ScheduleTransactionError("Power must be raw percent 1–100")
        result.append((n,start,end,mask,power))
    # Block overlapping active windows on a shared weekday.
    for i,a in enumerate(result):
        for b in result[i+1:]:
            if a[3]&b[3] and a[1]<b[2] and b[1]<a[2]:
                raise ScheduleTransactionError(
                    "Overlapping schedules on the same weekday are blocked")
    return sorted(result)


@dataclass(frozen=True)
class WriteStep:
    address:int
    value:int
    previous:int
    description:str


@dataclass(frozen=True)
class Plan:
    initial_charge:tuple[int,...]
    initial_discharge:tuple[int,...]
    desired_charge:tuple[int,...]
    desired_discharge:tuple[int,...]
    steps:tuple[WriteStep,...]
    changes:int

    def summary(self):
        return {
            "status":"SCHEDULE_PLAN_ONLY",
            "write_sent":False,
            "changes":self.changes,
            "register_writes_required":len(self.steps),
            "steps":[{"register":hex(s.address),"old":s.previous,
                      "new":s.value,"reason":s.description} for s in self.steps],
            "final_charge_mask":self.desired_charge[0],
            "final_discharge_mask":self.desired_charge[1],
            "warning":(
                "One explicit confirmation is required. If TOU is active, "
                "it is paused during edits and restored after verification. "
                "Changes to several registers are NOT atomic; "
                "if interrupted, manual inspection/recovery is required."
            ),
        }


def build_plan(snapshot, *, expected_charge, expected_discharge,
               proposed_charge, proposed_discharge):
    charge0, discharge0, config=validate_snapshot(snapshot)
    if _expected_rows(expected_charge)!=active_rows(config,"charge"):
        raise ScheduleTransactionError(
            "eLEKeeper/another controller changed charge schedules; reload draft")
    if _expected_rows(expected_discharge)!=active_rows(config,"discharge"):
        raise ScheduleTransactionError(
            "eLEKeeper/another controller changed discharge schedules; reload draft")

    charge=list(charge0);discharge=list(discharge0)
    specs=(
        ("charge",_desired_rows(proposed_charge),charge,BASE_CHARGE),
        ("discharge",_desired_rows(proposed_discharge),discharge,BASE_DISCHARGE),
    )
    steps=[]
    for direction,rows,words,base in specs:
        enable=0
        for n,start,end,mask,power in rows:
            enable|=1<<(n-1)
            packed=(mask<<8)|power
            new_words=(clock(start),clock(end),packed)
            word_offset=(2 if direction=="charge" else 0)+3*(n-1)
            old_start=words[word_offset]
            old_end=words[word_offset+1]
            # Existing enabled slots remain active during a multi-write
            # change. Choose an order that never temporarily produces
            # start >= end. For a later time window, extend end FIRST.
            currently_enabled=bool(
                (charge0[0] if direction=="charge" else charge0[1]) &
                (1<<(n-1))
            )
            order=(1,0,2) if (
                currently_enabled and new_words[0]>=old_end and
                old_start<new_words[1]
            ) else (0,1,2)
            for j in order:
                value=new_words[j]
                idx=word_offset+j
                if words[idx]!=value:
                    steps.append(WriteStep(
                        base+3*(n-1)+j,value,words[idx],
                        f"{direction} slot {n} {'start' if j==0 else 'end' if j==1 else 'days/power'}"
                    ))
                    words[idx]=value
        if direction=="charge":
            charge[0]=enable
        else:
            charge[1]=enable
    # Masks must be committed last so new slots aren't active with stale data.
    if charge0[0]!=charge[0]:
        steps.append(WriteStep(CHARGE_START,charge[0],charge0[0],"charge enable mask"))
    if charge0[1]!=charge[1]:
        steps.append(WriteStep(CHARGE_START+1,charge[1],charge0[1],"discharge enable mask"))
    if len(steps)>MAX_WRITES_PER_ACTION:
        raise ScheduleTransactionError("Too many register writes in one action")
    return Plan(
        tuple(charge0),tuple(discharge0),tuple(charge),tuple(discharge),
        tuple(steps),len(steps),
    )


async def read_full(client):
    method=client.read_holding_registers
    unit="device_id" if "device_id" in inspect.signature(method).parameters else "slave"
    async def read(addr,count):
        r=await method(address=addr,count=count,**{unit:UNIT_ID})
        if r is None or r.isError() or len(r.registers)!=count:
            raise ScheduleTransactionError(f"Invalid Modbus read {hex(addr)}")
        return tuple(r.registers)
    async def once():
        charge=await read(CHARGE_START,CHARGE_COUNT)
        discharge=await read(DISCHARGE_START,DISCHARGE_COUNT)
        mode=(await read(MODE_ADDR,1))[0]
        fallback=(await read(FALLBACK_ADDR,1))[0]
        return charge,discharge,decode_config(charge,discharge,mode,fallback)
    first,second=await once(),await once()
    if first!=second:
        raise ScheduleTransactionError("Inverter changed during full double-read")
    return validate_snapshot(second)


async def execute_plan(
    *, host, port, confirmation, device_model, control_firmware,
    expected_charge,expected_discharge,proposed_charge,proposed_discharge,
    transport=AsyncModbusTcpClient, sleep=asyncio.sleep,
):
    if confirmation!=CONFIRM_PHRASE:
        raise ScheduleTransactionError("Exact manual confirmation required")
    if device_model!="H2-10K-S3-A" or control_firmware!="v2.018":
        raise ScheduleTransactionError("Unsupported inverter firmware/profile")
    if not host or type(port) is not int or not 1<=port<=65535:
        raise ScheduleTransactionError("Invalid network destination")
    client=transport(host,port=port,timeout=5,retries=0)
    attempted=[]
    try:
        if not await client.connect():
            raise ScheduleTransactionError("Could not open inverter connection")
        baseline=await read_full(client)
        plan=build_plan(baseline,expected_charge=expected_charge,
            expected_discharge=expected_discharge,
            proposed_charge=proposed_charge,proposed_discharge=proposed_discharge)
        if not plan.steps:
            return {"status":"NO_CHANGE","write_sent":False,
                    "message":"Inverter schedules already match"}
        if await read_full(client)!=baseline:
            raise ScheduleTransactionError("Concurrent change before write: blocked")

        write=client.write_register
        unit="device_id" if "device_id" in inspect.signature(write).parameters else "slave"
        charge=list(plan.initial_charge);discharge=list(plan.initial_discharge)
        for step in plan.steps:
            # No retry even if prior operation's ACK was lost.
            attempted.append(hex(step.address))
            ack=await write(address=step.address,value=step.value,**{unit:UNIT_ID})
            if ack is None or ack.isError():
                raise ScheduleTransactionError(
                    "Write acknowledgement absent at "+hex(step.address)+
                    ". Outcome uncertain; DO NOT retry automatically")
            if CHARGE_START<=step.address<CHARGE_START+CHARGE_COUNT:
                charge[step.address-CHARGE_START]=step.value
            elif DISCHARGE_START<=step.address<DISCHARGE_START+DISCHARGE_COUNT:
                discharge[step.address-DISCHARGE_START]=step.value
            else:
                raise ScheduleTransactionError("Invalid planned address")
            await sleep(1)
            readback=await read_full(client)
            if (readback[0]!=tuple(charge) or readback[1]!=tuple(discharge) or
                readback[2].mode!=baseline[2].mode or
                readback[2].fallback!=baseline[2].fallback):
                raise ScheduleTransactionError(
                    "Unexpected register change after "+hex(step.address)+
                    "; STOPPED. Partial changes possible")
        return {
            "status":"SCHEDULE_VERIFIED_BY_MODBUS",
            "write_sent":True,
            "registers_written":len(attempted),
            "verified_charge_mask":charge[0],
            "verified_discharge_mask":charge[1],
            "mode_unchanged":True,"fallback_unchanged":True,
            "message":(
                "Each register confirmed against full inverter readback. "
                "Verify saved schedules in eLEKeeper. Cloud UI may lag."
            ),
        }
    except Exception:
        if attempted:
            _LOGGER.exception(
                "Partial TOU schedule write possible; attempted %s. "
                "Manual eLEKeeper review required",attempted)
        raise
    finally:
        client.close()
