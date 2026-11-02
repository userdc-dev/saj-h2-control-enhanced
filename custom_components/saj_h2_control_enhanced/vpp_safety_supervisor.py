"""Persistent VPP safety supervisor — DRY RUN / NO INVERTER WRITES.

This release has no live dispatch, no TOU changes, and no automatic rollback.
It rehearses timing, journaling, monitoring and restart recovery while holding
a complete double-verified read-only snapshot for future engineering tests.

SAJ TOU slots are WEEKLY recurring. No software watchdog can guarantee
hardware cleanup while Home Assistant or the inverter is unreachable.
"""
from __future__ import annotations

import asyncio
import copy
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from uuid import uuid4

from homeassistant.helpers.storage import Store

SCHEMA = 1
ACTIVE = frozenset(("rehearsal_scheduled", "rehearsal_running"))
TERMINAL = frozenset((
    "idle", "rehearsal_completed", "rehearsal_cancelled",
    "rehearsal_interrupted", "review_required",
))
STATUSES = ACTIVE | TERMINAL
MAX_AUDIT = 24
# This is a build-time safety gate, NOT a user setting.
LIVE_INVERTER_WRITES_ENABLED = False


class SupervisorError(RuntimeError):
    """Cannot safely load, journal or advance a proposed VPP action."""


def aware_utc(value):
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise SupervisorError("An aware UTC timestamp is required")
    return value.astimezone(timezone.utc)


def parse_utc(text):
    if not isinstance(text, str):
        raise SupervisorError("Invalid journal timestamp")
    try:
        dt = datetime.fromisoformat(text)
        return aware_utc(dt)
    except (TypeError, ValueError) as exc:
        raise SupervisorError("Invalid journal timestamp") from exc


def full_snapshot(snapshot):
    """Preserve every register, even inactive slots, without changing a byte."""
    if not isinstance(snapshot, (tuple, list)) or len(snapshot) != 3:
        raise SupervisorError("Double-read raw schedule snapshot is missing")
    charge, discharge, config = snapshot
    charge = list(charge)
    discharge = list(discharge)
    if len(charge) != 23 or len(discharge) != 21:
        raise SupervisorError("Wrong number of TOU registers")
    if any(type(n) is not int or not 0 <= n <= 65535
           for n in charge + discharge):
        raise SupervisorError("Unexpected TOU register value")
    if type(config.mode) is not int or type(config.fallback) is not int:
        raise SupervisorError("Operating mode or fallback is invalid")
    if config.mode not in (0, 1) or config.fallback not in (0, 1):
        raise SupervisorError("Unsafe/unsupported inverter mode")
    return {
        "charge_words": charge, "discharge_words": discharge,
        "mode": config.mode, "fallback": config.fallback,
    }


def snapshot_hash(raw):
    """Canonical hash for exact bit-for-bit *readback* comparison."""
    canonical = json.dumps(raw, sort_keys=True, separators=(",", ":"))
    return sha256(canonical.encode("utf-8")).hexdigest()


def empty_record():
    return {
        "schema": SCHEMA, "status": "idle", "run_id": None,
        "write_sent": False, "live_activation_supported": False,
        "audit": [], "last_error": None, "baseline": None,
        "baseline_hash": None, "started_utc": None, "ends_utc": None,
        "direction": None, "duration_minutes": None,
        "last_verified_utc": None, "baseline_check": "not_checked",
    }


def check_record(value, entry_id):
    """Reject unknown journals rather than assuming an inverter is safe."""
    if type(value) is not dict or value.get("schema") != SCHEMA:
        raise SupervisorError("Unknown supervisor journal schema")
    if value.get("entry_id") not in (None, entry_id):
        raise SupervisorError("Supervisor record belongs to another inverter")
    if value.get("status") not in STATUSES:
        raise SupervisorError("Unknown/unreconciled supervisor state")
    if value.get("write_sent") is not False or (
        value.get("live_activation_supported") is not False
    ):
        raise SupervisorError("Journal claims possible inverter writes")
    if value.get("status") in ACTIVE | {
        "rehearsal_interrupted", "review_required", "rehearsal_completed"
    } and value.get("baseline") is not None:
        baseline = value.get("baseline")
        if type(baseline) is not dict or set(baseline) != {
            "charge_words", "discharge_words", "mode", "fallback"
        }:
            raise SupervisorError("Incomplete or invalid full TOU register journal")
        words = (baseline["charge_words"], baseline["discharge_words"])
        if (any(type(w) is not list for w in words) or
                len(words[0]) != 23 or len(words[1]) != 21 or
                any(type(x) is not int or not 0 <= x <= 65535
                    for group in words for x in group)):
            raise SupervisorError("Invalid persisted TOU raw register blocks")
        if baseline["mode"] not in (0, 1) or baseline["fallback"] not in (0, 1):
            raise SupervisorError("Invalid persisted mode/fallback")
        if snapshot_hash(baseline) != value.get("baseline_hash"):
            raise SupervisorError("Full TOU snapshot fingerprint mismatch")
    if value.get("status") in ACTIVE:
        begin = parse_utc(value.get("started_utc"))
        end = parse_utc(value.get("ends_utc"))
        if not begin < end or (end-begin).total_seconds() > 65*60:
            raise SupervisorError("Invalid pending dispatch window")
        if value.get("baseline") is None:
            raise SupervisorError("Unverified full TOU baseline fingerprint")
    if not isinstance(value.get("audit"), list):
        raise SupervisorError("Journal audit history missing")
    return copy.deepcopy(value)


class VPPSafetySupervisor:
    """One per HA config entry. Save-before-state-transition; fail closed."""

    def __init__(self, hass, entry, *, store=None, clock=None):
        self.entry_id = entry.entry_id
        self._store = store if store is not None else Store(
            hass, 1, f"saj_h2_vpp_supervisor_{entry.entry_id}"
        )
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._lock = asyncio.Lock()
        self.record = empty_record()
        self.record["entry_id"] = self.entry_id

    def _now(self):
        return aware_utc(self._clock())

    def status(self):
        result = copy.deepcopy(self.record)
        # A full raw schedule snapshot is stored locally but must not be sent
        # to every browser tab. Only its fingerprint/verification is shown.
        result.pop("baseline", None)
        result["write_sent"] = False
        result["live_activation_supported"] = False
        result["can_dispatch"] = False
        result["display_warning"] = (
            "Read-only rehearsal. NO charge/discharge command was sent. "
            "Live VPP dispatch remains LOCKED pending hardware verification."
        )
        return result

    async def _commit(self, value):
        # Persist the entire record BEFORE exposing a changed state.
        # A failed save cannot advertise a running action.
        await self._store.async_save(copy.deepcopy(value))
        self.record = value

    def _transition(self, status, event, now, *, error=None, **fields):
        next_record = copy.deepcopy(self.record)
        next_record.update(fields)
        next_record["status"] = status
        next_record["last_error"] = error
        next_record["audit"] = (
            next_record.get("audit", []) + [{
                "time_utc": now.isoformat(),
                "event": event,
                "status": status,
                "write_sent": False,
            }]
        )[-MAX_AUDIT:]
        next_record["write_sent"] = False
        next_record["live_activation_supported"] = False
        return next_record

    async def load(self):
        """Restart: an unfinished session is INTERRUPTED, never resumed blindly."""
        async with self._lock:
            try:
                saved = await self._store.async_load()
                if saved is None:
                    return self.status()
                self.record = check_record(saved, self.entry_id)
                if self.record["status"] in ACTIVE:
                    next_record = self._transition(
                        "rehearsal_interrupted", "home_assistant_restarted",
                        self._now(),
                        error="Rehearsal interrupted by restart. No inverter writes "
                              "were ever permitted by this supervisor.",
                        baseline_check="needs_readback",
                    )
                    await self._commit(next_record)
            except Exception as exc:
                # Do not overwrite corrupted/unknown journal evidence.
                self.record = empty_record()
                self.record.update(
                    entry_id=self.entry_id, status="review_required",
                    last_error="Cannot trust persisted VPP journal: "
                               +type(exc).__name__+": "+str(exc),
                    baseline_check="not_checked",
                )
            return self.status()

    async def begin_rehearsal(self, preview, snapshot):
        """Explicit dry run after a fresh double-read and green preflight."""
        if LIVE_INVERTER_WRITES_ENABLED:
            raise SupervisorError("Live VPP writes are not implemented")
        async with self._lock:
            if self.record["status"] in ACTIVE | {"review_required", "rehearsal_interrupted"}:
                raise SupervisorError(
                    "Previous session unresolved; review/acknowledge before starting"
                )
            if type(preview) is not dict or preview.get("status") != "VPP_PREFLIGHT_ONLY":
                raise SupervisorError("Only a fresh read-only preflight can start a rehearsal")
            if (preview.get("write_sent") is not False
                    or preview.get("live_activation_supported") is not False
                    or preview.get("can_start") is not False
                    or preview.get("preflight_passed") is not True):
                raise SupervisorError("VPP preflight not cleared for simulation")
            duration = preview.get("duration_minutes")
            if type(duration) is not int or duration not in (5, 10, 60):
                raise SupervisorError("Unsupported dispatch duration")
            direction = preview.get("direction")
            if direction not in ("charge", "discharge"):
                raise SupervisorError("Unsupported dispatch direction")
            begin = parse_utc(preview.get("planned_start_local"))
            end = parse_utc(preview.get("planned_end_local"))
            now = self._now()
            if not (now < begin <= now.replace(microsecond=0)
                    + timedelta(minutes=5)):
                raise SupervisorError("Preflight start time expired or too far in future")
            if int((end-begin).total_seconds()) != duration*60:
                raise SupervisorError("Preflight deadline and duration disagree")
            raw = full_snapshot(snapshot)
            record = self._transition(
                "rehearsal_scheduled", "rehearsal_journaled", now,
                run_id=str(uuid4()), entry_id=self.entry_id,
                started_utc=begin.isoformat(), ends_utc=end.isoformat(),
                duration_minutes=duration, direction=direction,
                baseline=raw, baseline_hash=snapshot_hash(raw),
                baseline_check="verified_at_start",
                last_verified_utc=now.isoformat(),
                proposed_slot=preview.get("proposed_slot"),
                requested_raw_percent=preview.get("requested_power_percent_raw"),
            )
            await self._commit(record)
            return self.status()

    async def tick(self, *, snapshot=None):
        """A HA heartbeat; NEVER touches a register or silently restores."""
        async with self._lock:
            if self.record["status"] not in ACTIVE:
                return self.status()
            now = self._now()
            start = parse_utc(self.record["started_utc"])
            end = parse_utc(self.record["ends_utc"])
            if now < start:
                return self.status()
            if now < end:
                if self.record["status"] == "rehearsal_scheduled":
                    await self._commit(self._transition(
                        "rehearsal_running", "simulated_window_open", now
                    ))
                return self.status()
            check = "not_checked"
            if snapshot is not None:
                try:
                    check = ("unchanged" if snapshot_hash(full_snapshot(snapshot)) ==
                             self.record["baseline_hash"] else "changed_externally")
                except SupervisorError:
                    check = "readback_invalid"
            new_status = ("rehearsal_completed" if check == "unchanged"
                          else "review_required")
            await self._commit(self._transition(
                new_status, "simulated_window_ended", now,
                baseline_check=check,
                last_verified_utc=now.isoformat() if check=="unchanged" else None,
                error=(None if check=="unchanged" else
                       "Read-only test finished, but exact original TOU state "
                       "could not be verified. Inspect inverter; no writes sent."),
            ))
            return self.status()

    async def verify_baseline(self, snapshot):
        """Read-only exact comparison; never silently overwrite another actor."""
        async with self._lock:
            if self.record.get("baseline") is None:
                raise SupervisorError("No retained baseline to verify")
            now = self._now()
            try:
                compared = snapshot_hash(full_snapshot(snapshot))
                result = ("unchanged" if compared == self.record["baseline_hash"]
                          else "changed_externally")
            except SupervisorError:
                result = "readback_invalid"
            pending = self.record["status"] in ACTIVE
            new_status = (self.record["status"] if result == "unchanged"
                          else "review_required")
            if pending and result != "unchanged":
                new_status = "review_required"
            next_record = self._transition(
                new_status, "explicit_read_only_baseline_check", now,
                baseline_check=result,
                last_verified_utc=now.isoformat() if result=="unchanged" else None,
                error=(None if result=="unchanged" else
                       "Stored baseline does not match device; manually inspect "
                       "all 7+7 schedules before further use."),
            )
            await self._commit(next_record)
            return self.status()

    async def cancel(self):
        """Cancels only the SIMULATED rehearsal; never implies hardware stop."""
        async with self._lock:
            if self.record["status"] not in ACTIVE:
                raise SupervisorError("There is no active read-only rehearsal to cancel")
            now = self._now()
            await self._commit(self._transition(
                "rehearsal_cancelled", "user_cancelled_rehearsal", now,
                error=None,
            ))
            return self.status()

    async def acknowledge(self):
        """Explicitly clear a non-write recovery warning, keep audit trail."""
        async with self._lock:
            if self.record["status"] not in ("review_required", "rehearsal_interrupted"):
                raise SupervisorError("No interrupted or unverified rehearsal to acknowledge")
            now = self._now()
            await self._commit(self._transition(
                "idle", "user_acknowledged_read_only_recovery", now,
                error=None, baseline_check="acknowledged_not_verified",
                baseline=None, baseline_hash=None, started_utc=None,
                ends_utc=None, run_id=None,
            ))
            return self.status()
