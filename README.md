# SAJ H2 Control Enhanced — DESIGN ONLY

> **For any future developer or AI assistant: [READ DEVELOPER_HANDOFF.md FIRST](DEVELOPER_HANDOFF.md).** This is the canonical record of project goals, decisions, previous chat history, safety restrictions, architecture, milestones and exact implementation status. Do not implement control writes based on the README alone.

**Status:** first separate read-only Home Assistant TOU preview v0.1.0 committed, not yet field-tested. **No live inverter write controls.**

This is a separate project from [SAJ H2 Safe Enhanced](https://github.com/userdc-dev/saj-h2-safe-enhanced), the owner's functioning read-only Home Assistant integration. The existing read-only repository must remain untouched by writable control development.

## Planned functionality

- **Quick actions:** charge or discharge the battery for a chosen number of minutes, with power bounded by verified hardware capabilities.
- **Schedules:** configurable charging/discharging days, time windows and time-of-use rules.
- **Safety:** explicit user confirmation, cancel, timeout, independent watchdog, state readback and verified restoration.
- **UI:** compact controls in the space freed beneath the SAJ Energy Live flow; no oversized battery gauge or redundant PV cards.

## Non-negotiable restrictions

- **Never command Backup mode 2 or Off-grid/Passive mode 3.** Mode 3's name is inconsistent between upstream code and the owner's experience.
- Don't change battery reserve SOC, depth of discharge, BMS protections, charging voltage or export limits.
- No arbitrary `max power` commands. Discover and validate the exact inverter/battery permissible ratings first.
- Don't begin any operation when readings are stale, control ownership is unclear, or expected safe stop/recovery isn't proven.
- No automatic mode switching, or persistent active actions, until separate authorized safety testing.

## Current hardware context

SAJ H2 10 kW AC inverter; 30 × 440 W bifacial panels; SAJ battery **40.00 kWh capacity reported by SAJ app**, not 40.96. Existing read-only Modbus monitoring uses device ID 1; operating-mode read register 0x3647. Any public repository should not contain private LAN addresses, precise home coordinates or passwords.

## Development status and next steps

1. **Milestone 0 complete:** separate repository, project handoff, safety roadmap, non-functional control preview and safety-policy tests committed.
2. **Control-core groundwork:** [validated telemetry adapter](control_core/telemetry.py), [non-executable action review](control_core/planner.py), [telemetry contract](docs/TELEMETRY_CONTRACT.md), and automated offline [safety tests](.github/workflows/safety-tests.yml).
3. **Next:** design interactive UI with all actions disabled; research read-only hardware status and control ownership; design and unit-test safe timeout/stop state machine.
4. Hardware-write work requires a distinct explicit approval and controlled testing. **No control implementation is installed in Home Assistant.**

See [Developer Handoff](DEVELOPER_HANDOFF.md), [Safety and Roadmap](docs/SAFETY_AND_ROADMAP.md), [Project Handoff](docs/PROJECT_HANDOFF.md), [Mock Dashboard Card](examples/compact-control-preview.yaml) and [Safety Tests](tests/test_safety_policy.py).

For all prior confirmed read-only register mappings, commissioning and v0.3.x dashboard history, consult the [read-only project handoff](https://github.com/userdc-dev/saj-h2-safe-enhanced/blob/main/PROJECT_HANDOFF.md).

**New SAJ app evidence:** [TOU screenshot observations & required bidirectional device synchronization](docs/SAJ_APP_TOU_OBSERVATIONS.md) documents 7 charge + 7 discharge slots, weekday multiselect, 0–9900 W discharge UI range, TOU fallback to Self-consumption, and owner's observed up-to-5-minute activation delay. Device-side schedules/settings must be read back; local drafts must not masquerade as confirmed inverter state.

**Long-term roadmap:** [OCPP EV charging and air-conditioning/major-load coordination](docs/FUTURE_SMART_LOADS.md) — future only, conditioned on verified inverter controls, device readback and eLEKeeper consistency.

## Installable read-only TOU preview

[Integration source](custom_components/saj_h2_control_enhanced) · [Install and verify](docs/READ_ONLY_HA_PREVIEW.md). Publishes actual inverter mode, unscheduled fallback, schedule counts and active 7+7 charge/discharge schedule details as read-only Home Assistant sensors; updates every 120 seconds by default. Existing `saj_h2_safe` is unchanged. Not installed or field-tested yet; no write functions.
