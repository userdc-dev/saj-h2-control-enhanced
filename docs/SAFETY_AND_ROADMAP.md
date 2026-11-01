# Safety gates and delivery milestones

> **Historical safety-plan document; NOT the current implementation status.** The current working Home Assistant integration has mode controls, schedule editing and fallback controls. The authoritative, complete current safety contract, hardware evidence, tests and open issues are in [DEVELOPER_HANDOFF.md](../DEVELOPER_HANDOFF.md). Statements below such as “planning only”, “no Modbus write code” and “next UI preview only” describe earlier milestones and **must not be used to deny the existence of actual control paths**. Do not confuse passing offline tests with full physical-inverter certification.


## Milestone 0 — repo and planning (CURRENT)
- Separate project from `saj-h2-safe-enhanced`.
- Requirements, read-only existing sensors, blocked mode codes and model assumptions captured.
- No Modbus write code.

## Milestone 1 — UI preview ONLY
- Compact dashboard controls: Charge for X min, Discharge for X min, Start/Cancel; weekly charging/discharging schedule form; weekday and time selection.
- All actions explicitly display `Preview only — no inverter control` and cannot submit a live action.
- Show safety warnings without overloading the interface.

## Milestone 2 — evidence collection and non-write state machine
- Confirm with manufacturer documentation or direct read-only registers: permitted operating modes, charge/discharge power limits, schedules, write permissions, existing third-party control state, reserve, BMS status and fallback behaviour.
- Define a strict model- and firmware-specific allowlist; never reuse guessed mappings across variants.
- Test state transitions, conflict rejection, timeout, cancel, reboot, DST and HA disconnect using synthetic hardware.

## Milestone 3 — owner-authorized bench test
- Only after explicit approval: isolated/safe test harness with controlled single-purpose writable service.
- Never send backup/off-grid/passive commands or change depth-of-discharge/BMS safety parameters.
- Verify precondition snapshot, final mode, response, status readback and rollback. No unattended operation.

## Milestone 4 — controlled integration
- Disabled by default and clearly separate from the read-only integration.
- Explicit confirmation before action, clamps and maximum duration, real-time watchdog, timer cancellation, audit log, user-visible recovery and scheduler enable switch.
- Charge/discharge action must stop safely if user cancels, data goes stale, or any protection limit is reached.

## Questions to resolve before ANY write
- Which exact H2 firmware profile and which third-party controller currently asserts control?
- Is a mode change needed for manual charge/discharge, and can it be done entirely with modes 0 and 1?
- What is the actual permitted charge/discharge power/current and frequency of writing?
- How do forced action and weekly schedule interact with existing SAJ schedules and solar self-consumption?
- What does a safe stop mean on this hardware? Can restoration be proven via readback?
- What are the battery reserve and upper/lower SOC thresholds for safe operations?

**If any answer is unknown: no write.**

## SAJ app evidence and sync acceptance gate (2026-11-01)

See [SAJ_APP_TOU_OBSERVATIONS.md](SAJ_APP_TOU_OBSERVATIONS.md). Before adding any writable TOU feature, demonstrate **read-only** device-side synchronization for overall mode, 7 charge + 7 discharge slots, start/end, weekday mask, power and unscheduled fallback. Validate user-edited SAJ app changes arrive in HA, expose pending vs verified status, account for observed 5-minute propagation, and reject conflict/unknown registers. Default unscheduled TOU mode to Self-consumption, not Standby. Never touch Off-grid load backup or AC Coupling toggles. No write attempts during this stage.
