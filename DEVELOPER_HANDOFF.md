# DEVELOPER HANDOFF — SAJ H2 Control Enhanced

**Last updated:** 2026-11-01 (Australia/Adelaide).  
**Canonical handoff for new developers / future AI assistants:** read this file **first**, then `README.md`, `docs/SAFETY_AND_ROADMAP.md`, and the authoritative monitoring handoff in [saj-h2-safe-enhanced](https://github.com/userdc-dev/saj-h2-safe-enhanced/blob/main/PROJECT_HANDOFF.md).

> **STATUS — PLANNING ONLY.** This repository contains documentation, a *non-functional* dashboard preview, and basic pure-Python policy tests. There is **NO operational Home Assistant control integration**, **NO Modbus write implementation**, and **NO installed charge/discharge functionality**. Never claim a command or schedule has been tested against the user's inverter.

## 1. Executive summary: why this repository exists

The user has a working **read-only SAJ H2 Safe Enhanced** Home Assistant integration. After iterating on a compact SAJ-app-like energy dashboard, the user requested using freed dashboard space for **active battery controls**: timed forced charging/discharging, time-of-use charging/discharging schedules, configurable durations, cancellation and visible remaining time.

The user explicitly recognized this as a *writing/control deviation* and instructed us to create a **separate new GitHub repository**. This repo is that separate control-development track. It is **not** intended to convert the already-working read-only monitor into a writable integration.

**Repositories:**
- **Control project (this repository):** https://github.com/userdc-dev/saj-h2-control-enhanced
- **Read-only monitor (leave read-only):** https://github.com/userdc-dev/saj-h2-safe-enhanced
- **Read-only monitor developer memory:** https://github.com/userdc-dev/saj-h2-safe-enhanced/blob/main/PROJECT_HANDOFF.md
- **Related solar forecasting Android app:** https://github.com/userdc-dev/personal-solar-estimater (background only, not a control implementation)

## 2. User's desired end state — functional requirements

### Quick actions

- “**Charge battery at max [verified safe] power for X minutes**.”
- “**Discharge battery at max [verified safe] power for X minutes**.”
- Duration is entered by user; show active state, expected end, count-down and actual battery power/SOC.
- Explicit **Cancel / Stop**; default to no active action.
- “Max power” is a **UI intention**, never a hardcoded fixed register value. Determine verified device-specific limits and BMS constraints, apply conservative caps, and distinguish nominal hardware ratings from limits permitted *right now*.

### Scheduled operation / time-of-use

- Recurring charging/discharging windows by **weekday(s), start/end clock time and optional duration**.
- Enable/disable each schedule, edit/remove, show next run and completed/aborted runs.
- Resolve overlaps, conflicts, missed runs, midnight crossing and Australia/Adelaide DST changes.
- Preserve user-configured normal **Self-consumption** operation outside authorized windows, *only if an exact safe restoration method has been validated*.
- The user wants **Time-of-use mode information**, not a dashboard overwhelmed by large gauge cards.

### Compact dashboard design

- Current read-only dashboard: `saj-energy/live` on Home Assistant.
- First row: **Live energy flow on left**, **Power · 24 hours graph on right**. Live panel shows Solar, House, Battery, Grid, Forecast columns. Battery represented concisely in header: *percentage, estimated kWh and a small progress bar*. Avoid duplicate SOC / stored-energy words and verbose labels.
- User specifically requested removing the **entire oversized second row** containing a huge battery SOC semi-circle, an additional Battery card and PV1/2/3 cards; this row was removed from the monitor repo's **GitHub dashboard YAML**. The future control panel may occupy that space, **but no control card is installed yet**.
- Future UI should be compact and cohesive: timed Charge, Discharge, Cancel, schedule editor, time-of-use status and power/SOC limits; no giant gauges.
- Read-only dashboard YAML modifications are separate from implementing control behaviour; **never present a mock preview as a working control**.

## 3. Project timeline and historical decisions

1. Built `saj-h2-safe-enhanced` starting from read-only Modbus polling; verified SOC, PV1–3 and live energy data against SAJ app.
2. Added live home demand, battery charging/discharging sign, self-consumption mode, daily/monthly/yearly kWh counters, 10-second live polling and SAJ-style energy dashboard. Grid direction sign remains provisional without a nonzero app comparison.
3. Added experimental solar forecasting based on Open-Meteo; recognized 10 kW inverter AC output cap **does not cap** combined PV generation when simultaneous DC battery charging is possible.
4. Corrected battery nominal capacity for SOC-based on-screen kWh from earlier 40.96 to the SAJ app-reported **40.00 kWh**. Example: 42% -> 16.80 kWh, not 17.20 kWh. This is **not** guaranteed energy available above reserve.
5. Reworked Live Energy Flow to be compact. User disliked a redundant oversized battery gauge, Battery details and PV input row; requested replacing that area with a control workspace.
6. User specifically prohibited modifying the working read-only repo to add speculative write functionality. New repo `saj-h2-control-enhanced` was created.
7. This separate control repo got a README, preliminary safety/roadmap doc, simple mock preview, and an initial policy test. No live controls have been written. **This handoff is now the canonical project memory.**

**Do not confuse:**
- Changes committed to GitHub with changes *installed* in Home Assistant.
- A mock control UI with a working one.
- Operating mode values read from Modbus with permission or knowledge to write those values.
- Static battery nominal capacity with usable capacity or live charging limit.

## 4. Relevant hardware and environment

- **Inverter:** SAJ H2 hybrid, nominal **10 kW AC** output rating.
- **Solar panels:** 30 × 440 W bifacial, about **13.2 kWp** DC installed.
- **Battery:** SAJ B2 installation; the official SAJ app reports **40.00 kWh** installed capacity. User describes 2 assemblies, each of 4 × 5 kWh battery modules plus BMS module. Exact firmware, software revision, BMS register schema, permissible control interface and power/current limits must be independently verified.
- **Energy flow:** PV may supply AC load/export and charge DC battery simultaneously; never infer an overall 10 kW PV limitation from the inverter's AC rating.
- **Home Assistant:** Docker container `homeassistant` on Debian mini PC. Host configuration under `/home/kamrui/compose-files/homeassistant/config`, mapped to `/config` inside container. Existing read-only component `custom_components/saj_h2_safe`. User SSHes into the Debian host from Windows PowerShell.
- **Local Modbus:** TCP port 502; unit/device ID 1 in installed read-only monitor. Existing read-only mode at register **0x3647**. **Do not place private LAN IP addresses or personal property addresses in this public repo**; retrieve connection parameters from HA config at deployment.
- **Current operation:** The official app has previously displayed **“Under third-party control”**. Identity/ownership of the controlling system and interactions with other software are unresolved. This is a critical blocker to writing.
- **Key distinction:** Some existing Home Assistant integrations may already implement controls. Before any write, inventory other control sources and ensure no conflicting controllers or concurrent Modbus connections can alter device state.

## 5. Confirmed versus uncertain Modbus facts

**Known from the read-only monitoring project:**
- Battery SOC raw holding register `0x406F`, scaling 0.01%; for example raw 4300 => 43.00%.
- Battery signed power: positive corresponds to **discharge**, negative to **charge**, verified against SAJ mobile app; see monitor repo `const.py` for exact register/scaling.
- PV input data starts around `0x4071`; home load `0x40A0`; raw signed grid power `0x40AD`.
- `0x3647` read sample `0` corresponds to **Self-consumption**.

**Operating mode interpretation from user's SAJ experience:**
- `0` — Self-consumption.
- `1` — Time-of-use.
- `2` — Backup — **forbidden to command**.
- `3` — Off-grid / Passive naming ambiguity — **forbidden to command**.
- **Reading** modes 2/3 for status display is not prohibited; **sending** either mode 2 or 3 is.

**NOT established:**
- Which register(s) actually permit safe forced charge/discharge, whether write is allowed by this firmware, signed/unsigned scaling, permitted power range, side effects, atomicity, control timeout, power direction and release/restore mechanism.
- Whether the operating mode register itself is writable, or whether forced actions require any mode change at all.
- Maximum charge/discharge rate and current for this exact model/configuration. The owner mentioned **10 kW as an illustrative possible battery charging limit**, **NOT as a confirmed setpoint**.
- What the official app's “third-party control” status means for authorization and arbitration.
- If a write acknowledgment implies the inverter actually accepted/sustained a setting.

Use the monitor repo and upstream `stanus74/home-assistant-saj-h2-modbus` for **research only**, not a license to copy unvalidated write sequences.

## 6. Non-negotiable safety boundary

1. **Never command mode 2 (Backup) or mode 3 (Off-grid/Passive).** The user reports harmful operational side effects. Do not attempt “temporary” excursions into either, including via hidden macros, reset routines, failure recovery, scheduler or tests on actual hardware.
2. **Leave `saj-h2-safe-enhanced` read-only and independently functional.** Write features belong only to this separate repo/domain.
3. **No live writes in the initial stages.** Tests run on fakes/simulated transports only. This repo currently has no Modbus write code.
4. Never touch reserve SOC, depth of discharge, BMS protection thresholds, charge voltage, grid-export compliance limits, anti-islanding or safety settings unless independently required and explicitly authorized—which is not currently the case.
5. **Fail closed** if firmware isn't positively identified, live readings are stale/unavailable, conflicting third-party controller may be active, battery errors/limits exist, the pending action conflicts with existing timers/schedules, or a safe stop has not been verified.
6. **No arbitrary “max”:** hardware/BMS/current SOC/temperature/time-of-use constraints must be verified and power clamped. No hidden assumptions of 10 kW charge/discharge capability.
7. Never trust a Modbus write acknowledgment alone. Verify mode and power with independent **readback**, and reject/abort on disagreement.
8. Actions must have conservative fixed duration boundaries and a **device/backend watchdog**; the UI must not need to remain open.
9. Cancellation, restart, disconnection and lost-connection recovery must be tested. **No promise that a stop works unless it's demonstrably safe on the exact firmware.** If safe release cannot be guaranteed, do not enable the write feature.
10. Every change must be traceable in an audit log with intended command, user confirmation, observed result, timeout and restoration outcome. Redact secrets, precise location and unnecessary personal information.

**Mode 0/1 are not automatically approved for writing.** They are only candidates for future readback-informed safe planning. No live action is authorized by this document.

## 7. Proposed architecture and component boundaries

A separate Home Assistant custom integration, **candidate domain** `saj_h2_control_enhanced`, with modular responsibilities:

- **Read-only adapter** consumes the existing `saj_h2_safe` sensors for SOC, battery watts, errors, current mode and grid power. Do not copy/recreate all monitoring sensors.
- **Capability discovery** explicitly validates exact inverter model/firmware and supported operations. Unknown = disabled.
- **Control policy / safety gate** centralizes hard-deny mode codes, power/SOC/temperature bounds, stale-readings checks, time caps, and third-party conflict checks. No bypass via UI or service calls.
- **Request validation** converts the user action into typed plan (charge/discharge, minutes, verified limits, expected stop time), rejects invalid values.
- **State machine** states: `DISABLED`, `IDLE`, `VALIDATING`, `ARMED`, `RUNNING`, `STOPPING`, `VERIFYING_RESTORE`, `COMPLETED`, `FAILED_LOCKOUT`. Define explicit transitions, durable state, idempotence and watchdog.
- **Scheduler** timezone-aware recurring rules (weekly days and windows), overlap prevention, enabled/disabled states, DST and reboot handling; simulate first.
- **Transport abstraction** with `FakeTransport` for tests. A live writable transport is **not present** until the hardware/write milestone passes explicit review.
- **UI** clear distinction between simulated and live; optional confirmation, quick action countdown, cancel, next schedule, recent activity and a compact placement in dashboard.
- **Audit and recovery** persistent logs, states, action outcome and fallback verification.

Treat this as a **proposed** architecture, not implemented code. Avoid displaying an enabled “Charge” button unless backend safety enforcement is complete.

## 8. Development roadmap with gates and acceptance criteria

### M0 — Repository and durable knowledge (COMPLETE)
- Separate repo, README, roadmap, mock preview and preliminary policy tests.
- This document records goals, hardware assumptions, decisions, safety requirements and next steps.
- No deployed controller.

### M1 — Non-functional UI concept (NEXT)
- Compact interface with timed charge/discharge inputs, calendar/time-of-use configuration, cancel/status.
- Clearly labeled **Preview / disabled**; no backend write path.
- Visual review with the owner. Preserve main dashboard’s lean layout.
- Write tests for inputs and disabled-by-default safety posture.

### M2 — Hardware/firmware evidence and pure simulation
- Gather manufacturer/facility documentation and read-only diagnostics **without any write commands**.
- Inventory third-party control and conflicts; verify normal Self-consumption behavior.
- Document exact power and command constraints, response semantics, safe cancel/restore; reject unsupported devices.
- Build transport-independent state machine, schedule engine and deterministic fake data.
- Test cancellation, stale telemetry, timer expiry, missed runs, DST changes, reboot, duplicate requests, safety lockout and recovery.

### M3 — Owner-approved isolated hardware proof
- Require a **new, explicit authorization** for specific narrow write tests, based on documented registers and safe stop.
- No forbidden mode commands, no uncontrolled power, no unattended scheduling.
- Test one operation at a time; record readback, rollback and observed output. Stop immediately on inconsistency.

### M4 — Guarded Home Assistant controls
- Disabled by default, separately installed, explicit opt-in, visible confirmation and short initial maximum durations.
- Safe bounded power, independent watchdog, tested stop and restoration, full logs and no conflict with monitoring.
- Enable scheduling only after individual actions prove reliable over repeated controlled tests.

### M5 — Quality / UX
- Refine compact dashboard, persistent countdown, scheduling, warnings and historical usage; document known firmware limitations, support and rollback paths.

**Done = verified in the real system**, not merely present in GitHub.

## 9. Suggested initial tests (never touch hardware)

- `pytest` or pure Python unit tests for mode-deny list and type validation.
- Reject modes 2/3 regardless of API input type, direct service, schedule or UI.
- Reject durations <= 0, booleans, unsupported power setpoints, overlapping schedules and unknown device.
- Reject charge/discharge when monitoring is unavailable or too old.
- Verify restart cannot reactivate an expired action, test watchdog and idempotent Cancel.
- Verify timezone conversions in `Australia/Adelaide` including DST transition and overnight windows.
- Ensure no `write_register`, `write_coil` etc. code is shipped until specifically approved.
- Future bench test: command acknowledgements aren't enough, must independently read back state.

The existing `tests/test_safety_policy.py` is a **small design-only smoke test**, not proof of hardware safety.

## 10. Developer workflow and user communication preferences

- User prefers **very short instructions and one SSH command/action per turn**, awaiting “done” before moving to next step.
- When asked to modify GitHub, **edit/publish repo files directly** with connector, then link exact GitHub file/commit rather than dumping partial patches.
- Dashboard edits: provide **one complete, tested YAML file** and direct user to replace the raw dashboard YAML; avoid asking them to paste fragments.
- Avoid duplicate huge cards, excessive text, verbose sensor legends, or needless UI steps.
- User wants accurate units (W below 1 kW; kW above; Wh/kWh), and clear current vs estimated values.
- Never claim GitHub edits automatically update HA. State clearly whether a change is only committed, locally installed, tested or actually running.
- Before modifying the monitor repo or deploying anything, check with the user if it would affect the working read-only installation. Favor changes in this separate control repo.
- Save significant architectural decisions, confirmed device observations, failed tests and current work status in this handoff after each milestone.

## 11. Current inventory and implementation status (as of 2026-11-01)

| Item | Location | Status |
|---|---|---|
| Control project README | `README.md` | Written |
| Canonical developer handoff | `DEVELOPER_HANDOFF.md` | Written |
| Earlier short context / pointer | `docs/PROJECT_HANDOFF.md` | Exists; should point to this document |
| Safety milestones | `docs/SAFETY_AND_ROADMAP.md` | Planning document |
| Inert dashboard concept | `examples/compact-control-preview.yaml` | Mock only — no actions |
| Basic Python policy tests | `tests/test_safety_policy.py` | Small non-hardware test |
| HA `saj_h2_control_enhanced` integration | Not created | **Not implemented** |
| Writable Modbus transport | Not created | **Not implemented / prohibited until approval** |
| Charge/discharge actions | Not created | **Not implemented** |
| Scheduled commands | Not created | **Not implemented** |
| Tests on physical inverter | None | **Not authorized or performed** |
| Working read-only monitoring | External repo `saj-h2-safe-enhanced` | Independently installed; **do not modify writes** |

The read-only dashboard’s bulky second row was removed **in GitHub**; whether the user has copied this exact latest dashboard revision into Home Assistant is not independently confirmed.

## 12. Next actions for the very next development session

1. Read this handoff and both projects' current README and safety docs; inspect current repository files before editing.
2. **Design only** a clean compact control preview that visually fits the newly freed dashboard row. No active Modbus control buttons yet.
3. Prepare a model-specific question/evidence checklist for read-only verification of power limits, mode semantics and controller ownership.
4. Propose timer/schedule state machine schema and fake transport with unit tests; review safety boundaries.
5. Ask for/verify only missing firmware or register facts, **not the already-known hardware basics**.
6. Do not send any inverter mode changes or battery control commands. Do not move to M3 without new, explicit user approval.

## 13. Resuming from a new chat

Paste or say:

> Continue `userdc-dev/saj-h2-control-enhanced`. First read `DEVELOPER_HANDOFF.md` in that repo, `docs/SAFETY_AND_ROADMAP.md`, and the read-only repo's `PROJECT_HANDOFF.md`. Keep `saj-h2-safe-enhanced` read-only; never send modes 2/3. Resume from the current milestone and make GitHub updates directly. One step at a time for SSH.

**Security note:** This repository is public. Do not commit street addresses, exact coordinates, passwords, tokens, signing keys, private VPN endpoints, or personal details.

## 14. New progress — control-core telemetry groundwork (2026-11-01)

The user emphasized that existing read-only SAJ entities must be the **operational source of truth**, not just decorative dashboard entities. As requested, development has begun in **this separate control repository**, not the safe monitor:

- Added `control_core/telemetry.py`: names the known read-only HA entity IDs; validates numeric units and bounds, operating mode and battery activity, and rejects missing/unavailable states. It models a synchronized observation and requires an independently **verified successful Modbus poll heartbeat**.
- Added `control_core/planner.py`: reviews a proposed direction (charge/discharge), duration (design-only 1–120 min) and requested power, but **ALWAYS rejects execution**. “Max” is intentionally unresolved until exact inverter/BMS capability verification.
- Added `tests/test_telemetry.py` and GitHub Actions `.github/workflows/safety-tests.yml` for offline validation and a guard against Modbus writes.
- Added `docs/TELEMETRY_CONTRACT.md` describing exact source entities, their real measurement semantics, and missing safety-critical signals.
- **Not implemented:** HA control integration, actual entity subscriptions, verified poll heartbeat, power capability discovery, command registers, hardware writes, stop/recovery, schedule runner and working UI controls. No hardware control is authorized.
- **Critical insight:** HA `last_changed` / `last_updated` alone are not reliable source freshness; stable sensor values may not change even while polling, and stale values may linger after failure. The control integration must get a **verified source successful-poll timestamp** (and confirmed control ownership) before it can authorize requests. Do not bypass this for convenience.
- Next milestone: review/test the pure telemetry adapter against actual HA available entities and add a test-only finite-state timed-action/schedule simulator; plan independent source heartbeat without introducing dangerous writes or damaging the safe integration.


## 15. SAJ mobile app TOU screenshots and synchronization requirement (2026-11-01)

**Read [docs/SAJ_APP_TOU_OBSERVATIONS.md](docs/SAJ_APP_TOU_OBSERVATIONS.md) before implementing any mode/TOU UI or protocol.** The owner provided screenshots documenting:
- Distinct **Current mode** Self-consumption vs Time-of-use, with Save.
- TOU **Charge Settings +** and **Discharge settings +**, reported max **7 independent charge and 7 discharge entries**.
- Each displayed discharge slot has start/end time, power in W, and Monday–Sunday **multi-select** (Select All available). Example **22:00–22:40**, **9900 W**, Wednesday; **[0–9900] W** displayed for *discharge* only, not validated device/BMS safe output.
- Independent **Non-charge/discharge time period settings** in TOU permits **Self-consumption** or **Standby**. Owner wants **Self-consumption by default**. This is a TOU fallback setting, **not the same as overall inverter operating mode**.
- Separate **Off-grid load backup enabled** toggle and **Off-grid AC Coupling** option are visible and must remain entirely untouched. Do not equate them with forbidden operating modes.
- Owner observes mode/TOU settings may take **up to roughly 5 minutes** to fully activate, often at :00/:05/etc. Treat this as observation, not guaranteed timing.
- **NON-NEGOTIABLE:** HA must read settings *from device*, including mode, charge/discharge time windows, power, days and TOU fallback, and reconcile when settings are changed via official SAJ app. Local drafts/pending writes must never be displayed as confirmed active until device-side readback and observed effective state. Never silently overwrite an external SAJ app change.
- We **do not yet know** the register schema for TOU slots and fallback; do not fabricate it. Read-only register discovery and owner-visible cross-checks required before any write.
- Mode 2/3 remain permanently excluded. Instant active settings and simple HA-only timers must not be misrepresented as equivalent to device-configured schedules.

**Status remains non-writing:** screenshot findings and sync contract committed as docs; no TOU register synchronization is implemented yet.

## 16. Longer-term goal: OCPP EV chargers and HVAC load coordination

The owner explicitly wants the SAJ + Home Assistant system, **once reliable**, to coordinate EV charging using **OCPP** (Open Charge Point Protocol) and other high-power loads including air conditioning. This is a future capability, **NOT implemented**. It must preserve HA↔SAJ eLEKeeper synchronization and use the read-only SAJ sensors as operational inputs; avoid fighting device-native apps and schedules. Details, staged architecture and safety constraints are in [docs/FUTURE_SMART_LOADS.md](docs/FUTURE_SMART_LOADS.md). Do not claim fault-free operation; implement detection, fail-safe behaviour and recovery. Preserve the hard prohibition on writing modes 2/3.

## 17. TOU read-only decoder groundwork and new schedule limits (2026-11-01)

- The latest upstream `stanus74/home-assistant-saj-h2-modbus` reference maps charge-related holding registers **0x3604 count 23** (two enable bitmasks + seven 3-word charging slots) and discharge registers **0x361B count 21** (seven 3-word discharge slots). Overall mode **0x3647**; TOU unscheduled fallback **0x365F** (upstream labels 0 Standby, 1 Self-consumption). All of these mappings **remain unverified on this user's specific inverter**.
- Upstream slot encoding: start/end encoded as `(hour << 8) | minute`, power/day combined word high byte weekday mask and low byte **power percentage**. The owner reports SAJ app scheduling power range 0–9900 W and suspects 100 W steps; **possible raw-percent-to-watts scaling (99 ↔ 9900 W) is a hypothesis only**. DO NOT use unverified scaling to write registers. Weekday bit positions likewise require app parity check.
- The owner expressly confirmed **zero to seven** active charge schedules and independently **zero to seven** discharge schedules; NO minimum number. Empty masks and empty schedules are valid. All time display and validation **24-hour HH:MM**.
- Added `control_core/tou_readback.py`: PURE-PYTHON read-only 7+7 decoder, mask validation, strict 24-hour clock, mode and fallback, and external-config change diff; it **never marks mapping_verified=True**. Added `tests/test_tou_readback.py` for zero schedules, all seven, time bounds, drift, malformed data and mode restrictions. Linked test in GitHub Actions.
- **Next concrete investigation:** request one tightly bounded READ-ONLY Modbus snapshot from the owner for charge/discharge blocks, mode and fallback, then check actual values against matching eLEKeeper app settings. Do not infer active schedules from stale unused slot words; the enable bitmasks determine active rows. Do not attempt writes or toggle the inverter mode as a test.

## 18. Saved discharge power conversion now confirmed

Three paired actual inverter/app observations give **raw 100 → 9900 W, raw 98 → 9702 W, raw 50 → 4950 W**, so for this firmware's **discharge readback display**, `W = raw × 99`. `control_core/tou_readback.py` now exposes `discharge_display_watts` for offline readback formatting only. This does not validate write scaling, app rounding, charge scaling or device-rated operational safety. See [SAJ app TOU observations](docs/SAJ_APP_TOU_OBSERVATIONS.md). The device is presently in TOU mode (raw 1), with fallback Self-consumption (raw 1) and only Wednesday discharge slot enabled. No live battery control tests were performed.

## 19. First installable read-only Home Assistant TOU reader (2026-11-01)

The owner asked for faster substantive development. Committed `custom_components/saj_h2_control_enhanced` v0.1.0 as a separate Home Assistant config-flow integration. Its coordinator reads Modbus function 03 only: 0x3604 count 23, 0x361B count 21, 0x3647 mode, 0x365F outside-TOU fallback, then rechecks mode/masks/fallback. Default poll 120s to limit interference with existing `saj_h2_safe`. Publishes seven read-only sensors: mode, outside schedule fallback, charge/discharge active counts, schedule lists in attributes, and last device readback status/change counter. Discharge readback W=raw×99, verified against app at raw 50/98/100. Charge watts scaling and other weekday bits remain unverified. Unit tests in `tests/test_ha_tou_protocol.py`, CI includes test suite and no-write scan. Installation and rollback: `docs/READ_ONLY_HA_PREVIEW.md`. **This preview is committed but NOT installed/tested on user's HA yet. It has NO inverter writes, mode switch UI, schedule editor, or live charging commands.** Next: check CI, deploy only this custom component, confirm live HA entities match eLEKeeper, fix integration issues before expanding. Original read-only `saj_h2_safe` remains untouched.

## 20. Live installation milestone — HA TOU reader working (2026-11-01)

Owner installed `saj_h2_control_enhanced` on Kamrui and shared the Home Assistant device page **SAJ H2 TOU Readback**. Screenshot shows seven new sensor entities available, with saved settings reporting: Operating mode **Time-of-use**, Outside schedule behaviour **Self-consumption**, charge schedule count **0**, discharge schedule count **1**, and sync status **Readback OK (not verified with eLEKeeper live)**. This validates that the HA integration starts and obtains TOU register data; exact Wednesday time/power attributes need a separate check via **Discharge schedules → Attributes**. The older `saj_h2_safe` configuration was accidentally removed/re-added and dashboard temporarily broke due to mismatched entity IDs; user renamed entities back and confirmed the SAJ Energy dashboard restored. Maintain existing stable naming and do not modify/reinstall the old read-only monitor. Next test: inspect discharge schedules attributes and compare Wednesday 22:00–22:40, 4950 W (raw 50) to eLEKeeper; then test app-originated change propagation. **No HA Modbus writes are implemented.**

## 21. 2026-11-01: unattended development SESSION COMPLETED (without touching live inverter)

The user had to leave and asked for as much progress as possible in the current conversation. **No asynchronous work continues after the reply.** Work completed in the separate control GitHub repo only:

- Latest read-only HA TOU integration version bumped to **0.1.1**, **NOT deployed to Kamrui yet**. Existing **0.1.0** is working in Home Assistant. No new control functions.
- `custom_components/saj_h2_control_enhanced/__init__.py`: double-read the **entire charge and discharge register blocks**, overall mode and fallback within one read cycle; reject mismatching snapshots instead of accidentally accepting a partially saved schedule. Continue low-frequency polling (120s default) and no Modbus writes.
- `tou_protocol.py`: added `active_signature` and `describe_changes` so stale contents in DISABLED slots do not appear as actual eLEKeeper schedule changes. Unverified weekday masks are **not guessed**; Wednesday raw mask 4 is the only independently confirmed day.
- `sensor.py`: preserved all prior unique IDs/entity names, added `last_device_change` and `last_changes` attributes to sync sensor; change counts since startup.
- `examples/tou-compact-card.yaml`: read-only card for the existing HA dashboard, with actual mode, fallback, 0–7/7 slot counts, active schedules, confirmed Wednesday / unverified other weekday masks, confirmed discharge power W and source status. **Not auto-added to HA; requires Manual-card paste and entity ID check.**
- `control_core/reconciliation.py`: a pure-Python fail-closed state model of future submitted/pending/device-saved/unconfirmed/stale settings, with explicit source timestamp and timeout; **not wired into HA and cannot send any command**. `tests/test_reconciliation.py` covers old observations, no auto retries, mismatch, timeouts.
- Expanded `tests/test_ha_tou_protocol.py` for drift, disabled slots and weekday confidence.
- CI caught a Python syntax issue in coordinator changes; this was fixed in commits preceding **b9902709**, and CI subsequently passed. Check the **latest** GitHub Actions status after remaining documentation commits.
- `CHANGELOG.md` now documents the 0.1.1 upgrade and does not claim that GitHub updates auto-deploy.
- **Do not remove/re-add `saj_h2_safe` or `saj_h2_control_enhanced`**: user had to restore old monitor and rebind entity IDs after an accidental deletion. For updates, copy just the new control component folder over itself and restart HA, keeping integration entry and entity IDs unchanged. See `docs/READ_ONLY_HA_PREVIEW.md`.

### Immediate next owner-assisted work (one step at a time)

1. Owner returns. Verify the existing HA read-only `Discharge schedules` entity **attributes** include Wednesday 22:00–22:40, raw 50, saved 4,950 W. Screenshot of device page alone has confirmed only 1 configured, not contents.
2. Offer safe in-place upgrade to v0.1.1 (do not remove anything). The initial HA v0.1.0 is stable, so upgrade deliberately with rollback.
3. Optionally paste `examples/tou-compact-card.yaml` as a separate Manual card in SAJ Energy, adjusting any renamed entity IDs rather than removing the dashboard.
4. Check an **eLEKeeper-originated** schedule change propagates to HA with timestamp/change alert, without any Modbus write from HA.
5. Confirm charge-side schedule power scaling and weekday bits using app changes plus read-only Modbus. Charge watts conversion remains **unverified**; no control writes.
6. Before any real writable mode/charge/discharge testing, require a new user approval, hardware-specific safe command proof and safe stop/recovery. Never write modes 2 Backup or 3 Off-grid/Passive.

**Status boundary:** GitHub code updated and CI-tested, but `0.1.1` is not installed. Only `0.1.0` has been observed working live.

## 22. v0.2.0 dynamic dashboard, preview sliders and automatic discovery (2026-11-01)

The user requested a **dynamic self-updating dashboard with all 0–7 charge and 0–7 discharge schedules**, day/time/power sliders, and automatic inverter discovery and entity matching.

**Implemented in GitHub under this separate repo, NOT deployed to Kamrui:**
- Version `0.2.0` in `custom_components/saj_h2_control_enhanced/manifest.json`; includes `frontend`, `http` and `lovelace` dependencies.
- `config_flow.py` discovers existing configured `saj_h2_safe` entries and offers them as a one-click selection instead of manual IP. Manual fallback if none. Existing v0.1.x entry unchanged; coordinator detects uniquely matching safe monitor host and follows its current host/port. Config entries with `source_monitor_entry_id` fail closed if that monitor disappears.
- `sensor.py` includes stable `saj_tou_role` and `saj_tou_entry_id` attributes even while source unavailable. **Original entity unique IDs preserved**.
- `frontend/saj-tou-dynamic-card.js`: custom card auto-discovers TOU device entities, groups by integration entry ID, includes device selector; reads mode, TOU fallback, 0–7/7 active schedule rows and live source status; supports 24h start/end inputs, seven weekday checkboxes and local-preview raw-% sliders, with discharge readback W=raw×99 (only this firmware profile). For charge watts and unverified weekday masks, avoids inventing conversion. Each row can be preview-added/removed up to 7. Local drafts not persistent; if no draft changes, UI sliders follow eLEKeeper readback, if editing, retain draft and show Reload draft from inverter.
- **Absolutely NO WRITE PATH or real action buttons.** All editors are front-end previews. An Apply-to-inverter button is disabled. We have not tested actual mode switches or direct writes.
- `frontend_setup.py`: registers static bundled card JS using `hass.http.async_register_static_paths` and frontend extra-JS loading; attempts to create a separate `SAJ TOU Control` Lovelace storage dashboard only when absent. Existing `SAJ Energy` never modified. HA storage dashboard internal APIs may change, so any error is caught/logged; user can add `type: custom:saj-tou-dynamic-card` to a Manual card if auto dashboard fails. **Auto dashboard not verified in owner's HA**.
- CI includes Python syntax/offline unit tests/guard against Modbus write functions plus JS `node --check`; confirmed run success at commits before documentation changes. Check current HEAD CI.
- Installation and limitations: [docs/DYNAMIC_DASHBOARD_V020.md](docs/DYNAMIC_DASHBOARD_V020.md). GitHub code edits **do NOT auto-update existing Home Assistant**.
- Next: in-place update the **control integration only**, do not delete or re-add entries, do not change `saj_h2_safe` or `SAJ Energy`; restart Home Assistant and check sidebar for `SAJ TOU Control`. Confirm device/role auto discovery and that all 0–7 slots and preview editors render; fix HA-specific frontend setup errors if any. Only then consider backend writing research under explicit user authorization and hard mode 2/3 exclusions.

**Critical promise boundary:** user requested operational sliders eventually but v0.2.0 is **only preview** because inverter write commands and safe cancellation have not been proven. Don't claim otherwise, and never run experimental Modbus writes without a new user-approved safety plan.

## 23. v0.2.0 deployed successfully; 24-hour formatting fix in v0.2.1 (2026-11-01)

Owner provided an Android screenshot of the **automatically created "Time of Use" dashboard**, proving the custom JS card loaded and discovered the SAJ H2 TOU Readback device automatically. It showed device mode **Time-of-use**, unscheduled fallback **Self-consumption**, zero enabled charging schedules, one enabled discharging schedule, discharge slot **Wednesday 22:00–22:40** (raw schedule shown with *browser-local 10:00 pm–10:40 pm*, the issue corrected), and **4950 W** matching the official eLEKeeper and Modbus readings. It rendered the preview-only mode/fallback selectors, 0–7 schedule sections, power slider, weekday selection, disabled Apply button and a live readback status. Thus the v0.2.0 dashboard card was successfully installed and field-tested; actual inverter writes remain unavailable.

**User-observed UI issue:** Although source data was `22:00–22:40` in 24-hour notation, browser-native `input type=time` formatted it as 12-hour AM/PM according to Android locale. Fixed in GitHub **v0.2.1**: use an explicit text field constrained to strict `HH:MM` 24h time, rejecting malformed entries, guaranteeing visually stable 24-hour display. Also format source last-read timestamp into browser local time rather than raw UTC ISO, and simplify device selector to omit internal entry ID suffix. CSS and JS code in `frontend/saj-tou-dynamic-card.js`; release cache bust URL updated to `?v=021`; version bumped to 0.2.1.

**Deployment status:** v0.2.0 running in owner's HA as screenshot; v0.2.1 only committed in GitHub and not installed yet. For upgrade, copy new control folder over existing and restart HA; no need to delete integration, re-enter IP, alter old safe monitor or replace dashboards. Browser hard refresh if cached resource persists. See `docs/DYNAMIC_DASHBOARD_V020.md` for general update procedure.

## 24. Android frontend cache issue and saved-vs-draft ambiguity — v0.2.2 (2026-11-01)

The owner installed 0.2.1 and shared Android Brave screenshots showing **the old 12-hour native time picker (10:00 pm) still in use** despite 0.2.1 having changed the frontend source to a strict `HH:MM` text input. This indicates the browser was likely still loading a previously registered/custom-element JS implementation (old cached resource or long-lived HA SPA). The same screenshot showed **9603 W**, but this was the user's MOVED LOCAL DRAFT SLIDER, **NOT CONFIRMED stored inverter watts**. Do not treat this as a device-side change.

**New GitHub v0.2.2, not yet deployed:** versioned absolute static JS URL `/saj-h2-tou/v022/saj-tou-dynamic-card.js` (separate pathname, not query only) to defeat normal URL-based cache; card badge now includes **Preview v0.2.2** so we can detect the actual loaded JS version in screenshot; display **Saved on inverter: ...** separately from **Draft power** slider. Both charge/discharge schedules remain read-only in HA; 24-hour HH:MM text source remains from v0.2.1. No Modbus write functions.

**Next owner-assisted step:** perform in-place control-component folder upgrade (never delete/recreate either HA integration), restart HA, then **fully close/reopen the HA browser tab or use private tab** to force a clean JS load. Check badge says v0.2.2, see explicit HH:MM field `22:00` rather than native Android clock-picker and confirm Saved 4950 W vs Draft W clearly. If old JS persists, inspect HA frontend Resources and duplicated global `add_extra_js_url`, and check served static JS's contents on Kamrui. Do not assume copying files alone updates the current browser runtime.

**Do not change SAJ read-only monitor / existing SAJ Energy dashboard.** Device itself remains on its own prior operating/schedule settings.

## 25. First Friday CHARGE readback confirmation, v0.2.3 (2026-11-01)

User completed official eLEKeeper Friday charging schedule with 22:00–22:40 and saved **4950 W**, while leaving Wednesday discharge 22:00–22:40 at **4950 W**. Read-only Modbus snapshot: charge block `[1,1,5632,5672,4146,0,827,6170,...]`; discharge `[5632,5672,1074,0,...]`; overall mode **1** Time-of-use; unscheduled TOU fallback **1** Self-consumption. **Charge raw 4146 = 0x1032 = Friday mask 16 + raw power 50**; confirms charge 50→4950 W for THIS power setting only. Previous Wednesday mask 4 and discharge raw50→4950 W remain confirmed. Both enable masks 1 (1 charge, 1 discharge). Remaining weekday bit mapping and charge power at other raw values are **not independently verified**.

**Developed GitHub v0.2.3 (NOT deployed yet)**: `tou_protocol.py` adds verified Friday and Wednesday weekday labels and combined mask20, charge saved 4950 W display only when raw50, and a `power_conversion_verified` boolean. Other charge powers remain raw percent / unknown W; no unjustified blanket ×99. HA sensor charging power status updated; dynamic card shows checked Friday, 4950 W saved on inverter, and distinguishes unknown mappings. Card matches saved attributes by ORIGINAL physical slot number instead of array position, so sparse enable masks behave correctly. Added offline regression tests from actual app/Modbus snapshot; manifest to v0.2.3 and frontend static URL to `/saj-h2-tou/v023/saj-tou-dynamic-card.js` for cache-busting; changelog and observations updated. No write methods added.

**Next step**: copy ONLY new control integration folder over existing v0.2.2, restart HA, reopen frontend browser tab, verify banner/card loads and charging schedule displays **Friday 22:00–22:40 4950 W** while Wednesday discharge remains unchanged. Do not delete/recreate HA integration and do not alter `saj_h2_safe` monitor or `SAJ Energy` dashboard. Further app-originated test at another charging watt value can validate scaling, weekday tests continue. Physical mode and TOU writes still NOT authorized; never send modes 2/3. 

## 26. Charging second power sample confirmed; v0.2.4 (2026-11-01)

Official eLEKeeper reopened after entering 7000 W on Friday charging schedule and displayed **6930 W**. Read-only Modbus had returned charge slot word **4166 = (16<<8)|70**, Friday mask 16, raw power 70; unchanged 22:00–22:40 and Wednesday discharge. Thus two charge canonical pairs confirmed **50→4950 W, 70→6930 W**, matching discharge mapping raw×99. Implemented **v0.2.4** in `tou_protocol.py` with charging readback `raw*99` for display, and `power_conversion_verified` true only for direct paired raw50/70; all other charge values labeled estimated (not individually verified). Card now shows saved charging watts and preview W estimates; regression tests updated. Frontend URL version `v024`, manifest 0.2.4. GitHub code is not yet deployed to user's Home Assistant (still v0.2.3) and still has NO write controls. For upgrade copy only control component in place and restart HA. Future test other day-mask bits and actual controlled command safety before any writes.
