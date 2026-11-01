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

