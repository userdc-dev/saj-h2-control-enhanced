# VPP Quick Actions — staged implementation and safety contract

**Current scope: v0.5.24, no-write preflight and persistent watchdog rehearsal. Live timed battery dispatch is still disabled.** The compact dashboard has a duration selector (5/10/60 min), **Preview max charge**, **Preview max discharge**, and **Return to Self-consumption**. The first two do **not** issue a Modbus write, arm a timer or create an automation. The Self-consumption action delegates to the existing confirmed `supervised_self_consumption_pilot` path and uses its original device-readback, confirmation and single-write safeguards.

## Development branch — active rehearsal battery SOC watchdog (not released)

The simulated VPP supervisor now performs **two fresh direct inverter SOC readings** during each active 20-second watchdog check using existing register `0x406F` and the shared device lock. It records the latest verified SOC for the status response without writing the persistence journal every poll. Missing/inconsistent SOC, failed communication or SOC >=95% during a charge rehearsal / <=10% during discharge causes a durable `review_required` warning and interrupts the **simulation only**. A full verified 7+7 TOU baseline readback and explicit acknowledgement are required before another rehearsal. Any finished rehearsal also requires its usual exact raw schedule verification.

**This is NOT a real emergency stop.** This logic never sends a physical inverter stop command, restores TOU slots, or guarantees action if HA is offline. The existing Return to Self-consumption command is a separate user-confirmed live control, not an automatic emergency recovery mechanism. Battery watts, battery temperature, BMS alarms and grid import/export have **not** been added as trusted live safety gates in this development branch: their device mapping, freshness semantics, sign, limits and hardware response require verification first. An SOC measurement alone does not establish battery safety.

Do not enable a real dispatch service based on these read-only rehearsal changes. The same weekly recurrence, verified hardware recovery, maximum charging validation and other commissioning gates below remain mandatory.

## v0.5.24 — Persistent safety-supervisor rehearsal (no inverter writes)

A real single-click timed battery command is **NOT** enabled. To commission its recovery system without risking repeated weekly TOU exports, this release adds a persistent, explicitly **read-only** watchdog rehearsal.

**Control → VPP quick actions → Safety supervisor** (collapsed by default):

1. Use **Preview max charge/discharge** with 5, 10 or 60 minutes. Preflight must pass.
2. Expand **Safety supervisor**. Click **Check status**, then **Run dry-run rehearsal**; explicitly confirm the *simulation-only* warning. The backend performs another fresh full double-read and checks SOC, overlapping schedules and weekday support. It saves the complete raw 23+21 TOU words, current mode and outside-TOU fallback, a SHA-256 fingerprint, absolute UTC deadline and an append-only bounded audit trail in a per-entry Home Assistant Store.
3. A Home Assistant scheduler ticks about every 20 seconds. It can advance `rehearsal_scheduled → rehearsal_running → rehearsal_completed` after comparing the **full** saved baseline against another verified double-read. A missing/changed/inconsistent readback results in **review_required**, not false success.
4. **Cancel rehearsal** stops only the simulated session—**NOT the actual inverter**. It saves the cancellation in the persistent journal.
5. After HA restarts mid-rehearsal, the stored session is marked **rehearsal_interrupted**; HA displays a persistent review notification and no automatic battery command is resumed. Run **Verify saved schedules** (fresh full double-read) and only **Acknowledge review** if the exact baseline matches.
6. Unknown/tampered journal schema, ambiguous write flags and failed storage are **fail-closed**. A write-ahead journal save must succeed before a dry-run transition becomes visible. The browser status API never exposes the raw saved schedule snapshot.

Services: `vpp_rehearsal_status`, `start_vpp_safety_rehearsal`, `cancel_vpp_safety_rehearsal`, `verify_vpp_safety_baseline` and `acknowledge_vpp_safety_warning` (all `SupportsResponse.ONLY`, all no-write). The **existing** `preview_vpp_dispatch` still works and also uses the same global Modbus command lock.

**What this does not provide:** No inverter writes, no guaranteed real hardware stop, no saved one-shot TOU schedule, no live charging/discharging, no wholesale dispatch, no curtailment and no recovery write. Software running on HA cannot guarantee clearing a weekly inverter schedule while HA/network/inverter is offline. The **physical 5-minute low-power supervised field test** and a proven fail-safe one-shot or manufacturer recovery method are still required before any real dispatch action is exposed.

Automated tests: `tests/test_vpp_safety_supervisor.py` covers save-before-state transitions, disk failure, raw 7+7 register integrity, reboot interruption, external schedule changes, missing readback, cancellation, strict simulation-only commands and lack of Modbus write methods. Frontend smoke exercises status, start and cancel service routing. Live physical commissioning remains outstanding.

## Why isn't one-click max power already armed?

This SAJ H2's TOU configuration is a **recurring weekly** set of seven charging and seven discharging windows. A "5 minute" Friday period may recur **every Friday** if it isn't cleaned up. HA or the inverter might restart, the LAN could fail, or an elekeeper/VPP remote command could interfere. The existing `schedule_transaction.execute_plan` deliberately has **no silent retry and no automatic rollback** after an uncertain Modbus response, because partial register edits can persist.

Full-power discharge raw 100 has been paired with the owner's inverter display. Raw 100 **charging** has *not* been separately verified; the actual maximum depends on firmware, SOC, BMS temperature and installation limits. The raw percent is not a guarantee of achieving a particular number of kW or exporting at that rate. When the inverter is already in TOU, existing live schedules may conflict. Changing 7+7 slot registers and switching mode needs readback and atomicity protections that a simple browser timer cannot provide.

Any future live feature must be explicitly authorized by the homeowner after tests and inverter-specific commissioning. Do not silently enable it because the UI, CI or offline planner says a schedule is valid.

## What is implemented

- `custom_components/saj_h2_control_enhanced/vpp_quick_preview.py` pure planner. Accepts only `charge`/`discharge`, durations 5/10/60 minutes and timezone-aware local now; proposes an at-least-2-minute-in-future start; examines a *double-read* current TOU snapshot; requires a free correct-direction slot and no existing overlapping enabled windows in **either** direction; refuses unverified standalone weekend bits, overnight and DST transitions; requires self-consumption as the already-saved outside-TOU fallback.
- Conservative battery SOC guards: refuse preview eligibility above/equal 95% for charging, below/equal 10% for discharging or missing SOC. These are a starting safety margin, not firmware/BMS limits. The HA-side service reads SOC locally instead of trusting a browser-provided number.
- `preview_vpp_dispatch` registered service uses the shared `pilot_lock`, a fresh `read_full()` double-verified readback, and returns `status=VPP_PREFLIGHT_ONLY`, `write_sent=false`, `can_start=false`, `live_activation_supported=false`, proposed local start/end/slot/power and blockers. **No Modbus write is authorized.** Data is not persisted, and no expired schedule is generated.
- Compact **VPP quick actions** section within the **Control** tab. Selecting a duration and previewing a direction displays the real preflight result and expanded diagnostics. **Return to Self-consumption** uses the existing `_requestMode(group,0,"supervised_self_consumption_pilot")` and its confirmation dialog, fresh readback checks and no-retry mode write. The existing schedule controls, prices, history, forecast and live overview are unchanged.
- `tests/test_vpp_quick_preview.py` and updated frontend smoke tests verify valid proposals, overlap, lack of free slots, weekday, overnight/DST, SOC, missing data, no-write API status and service called by two preview buttons. Existing `tests/test_supervised_mode_engine.py`, `tests/test_schedule_transaction.py` and safety checks still run.

## Minimum requirements before an ACTUAL VPP Start/Stop service can be offered

1. **Bench-tested 100% charge/discharge and grid export safety:** verify actual inverter firmware model/control board, BMS limits, power ramp, expected SOC reserve, maximum discharge/export constraints, temperature safety and whether a schedule overrides an active VPP/retailer command. Verify charging source is appropriate (grid versus solar) and site import/export limits.
2. **Never overwrite users' 7+7 schedules silently.** Have a dedicated, free slot with no overlaps. Back up full raw register blocks, masks, mode and fallback with fingerprints. Check full double-read immediately before writing. Validate the user has not edited schedules in elekeeper or another service since the preview.
3. **One-shot future window** and no recurrence: physically validate start/end boundary semantics, weekdays (including weekend separately) and DST. A stale weekly slot MUST NOT recur after the command window; ensure guaranteed cleanup or hardware-native one-shot expiration. Do not use a browser `setTimeout` as a restoration guarantee.
4. **Crash-safe supervisor:** durable journal storing the verified before/after exact values, UTC expiration, idempotency key and state transitions. On HA reboot, immediately recover pending tasks; on communication failure, raise a critical HA alert and require verification before any other write. Never declare restored without a fresh complete double-read. A watchdog can only attempt restoration; it cannot guarantee device changes while power or network is unavailable. Design around this failure mode before enabling any live feature.
5. **Safe stop and return:** explicit **Stop now**, **Return to prior state** and **Go to Self-consumption**. Abort/restore only if device still matches the expected temporary schedule; if VPP/app changed it, block and warn instead of overwriting someone else's settings. Restoration also needs anti-repeat protection and no overlapping command sessions.
6. **Fail-closed on ambiguous Modbus:** no automatic retry after a write may have been sent. Verify every changed register and mode, and all 14 schedule slots, using the physical inverter. Control actions should be accessible only to authorized HA users, with confirmation, audit log, event status, lock and device-level feedback.
7. **VPP/wholesale dispatch logic is separately gated:** live price feeds, negative FiT policy, battery cycling value, export/import rules, GST, minimum SOC, dispatch fees and retailer conditions should be validated *before* any optimizer can decide to send a command. The integration cannot claim AEMO pricing/dispatch authorization by itself.

## Deferred: solar generation curtailment

**Not implemented; do not change PV output limit or export control registers without a detailed manufacturer-level register map and tests.** The inverter might have separate PV MPPT power reduction, site export limit, anti-islanding and battery-charge priorities. Reducing the grid export setpoint is NOT necessarily the same as reducing solar generation. Test read-only identification, actual PV/battery/grid response, hard utility export constraints, failure/restart behaviour and recovery with supervision. Do not reinterpret TOU battery registers as PV curtailment.

## Test on owner's installation after upgrade

Go to **SAJ H2 Control → Control → VPP quick actions**, select **5 minutes**, and click **Preview max discharge**. Check that the response says **no writes sent** and whether a matching slot would be free. Try 10 minutes and 1 hour. Existing mode and charge/discharge schedules must remain unchanged. The **Return to Self-consumption** button can operate live (if TOU is active and readback passes) after the same existing confirmation dialog. **Do not use an untested tariff, wholesale price or external automation to call a live pilot service.**
