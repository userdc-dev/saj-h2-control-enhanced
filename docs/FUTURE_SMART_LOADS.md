# Future expansion: coordinated EV charging and major household loads

**Status:** FUTURE ROADMAP ONLY. No EV charger, air conditioner or other load control is implemented.

## Owner's goal (2026-11-01)

Once the SAJ H2 controller has proven reliable, the owner wants Home Assistant to coordinate **EV chargers using OCPP** (Open Charge Point Protocol) and major electrical loads including **air conditioning**, alongside solar generation, household demand, battery SOC and SAJ time-of-use schedules.

The whole system should be **dependable, fail-safe and in sync with the official SAJ eLEKeeper app**. Avoid competing schedules, surprise energy import/export and manual-app versus HA disagreement. No software can honestly promise zero faults; design for safe failure, recovery and visible discrepancies.

## Priorities and phases

1. **Reliable readback / reconciliation first.** Prove that Home Assistant can accurately read the inverter's actual operating mode, seven charge and seven discharge schedule slots, fallback outside TOU windows, and changes made in eLEKeeper; separately show pending, stored, and actually effective settings. These registers are not yet confirmed.
2. **Battery controls second.** Only after device-specific read/write verification, safe stop/rollback and explicit authorization: allow switching between modes 0 Self-consumption and 1 Time-of-use, bounded timed charging/discharging and weekday schedules. Never send mode 2 Backup or mode 3 Off-grid/Passive.
3. **Observe major household loads before controlling them.** Gather real-time house demand, PV, battery, grid flows and the available smart-meter measurements. The sign of SAJ grid-power sensor has not yet been validated under nonzero exchange.
4. **OCPP EV charging integration.** Future optional integration for compatible chargers; prefer native, standardized controls and charger reports, with a charger-specific capability profile and independent current limit, communication watchdog and vehicle/charger status. OCPP support varies by charger firmware and protocol version and is NOT guaranteed for all equipment.
5. **Air conditioning and major loads.** Only via their independently supported HA integrations and approved interfaces, taking comfort/temperature constraints, compressor minimum-on/off and anti-short-cycle protections into account. Do not rapidly cut mains power to HVAC equipment or high-current loads as a substitute for an appropriate controller.
6. **Energy orchestration policies.** Optional solar-surplus charging, off-peak charging, battery reserve protection, load shedding, peak import limits, TOU tariff planning, and user-selected priorities (house comfort vs car charging vs battery reserve). Start with advice/monitor mode, then owner-approved automatic actions.
7. **Audit and recover.** Display what the SAJ inverter, eLEKeeper, EV charger and HVAC *actually* report, with per-device timestamp and control ownership. Actions must be independently verified and automatically disabled if data is stale or the primary app/controller changes settings.

## Proposed high-level architecture

- **SAJ read-only monitor** (external repo): authoritative measured PV, house, SOC, battery, grid data.
- **SAJ control integration** (this repo): future independently enabled safe TOU/mode/timed-action adapter, reconciled to actual device settings and eLEKeeper.
- **OCPP adapter**: future separate charger interface. Charger power and state from charger/meter itself, not inferred entirely from SAJ grid data.
- **HVAC adapter**: future controller for AC units with local limits and manual overrides respected.
- **Energy coordinator**: optional higher-level decision engine that consumes validated snapshots from all adapters and calculates a desired plan. It must never directly bypass each adapter's safety gate.
- **Policy / priorities**: explicit user-facing overrides, schedules and tariffs; prevent multiple control sources from fighting each other.
- **Telemetry consistency**: synchronized snapshots with ages/quality flags. HA `last_changed` is not proof of recent device polling.
- **No single point of unsafe failure**: if inverter, charger, meter, HA or network data is missing, fall back to independently safe device behavior; retain manual control, and never repeatedly toggle rapidly.

## Essential guardrails

- Obey inverter/BMS limits, grid connection/export regulations and charger cable/vehicle limitations.
- **Do not force battery discharge to export** simply because the SAJ TOU app supports it; permissions and settings must be verified.
- Consider PV energy availability separately from 10 kW AC inverter output limit and battery charge path.
- Support eLEKeeper as a potentially independent writer. Never pretend HA's last requested values equal the current inverter settings; detect drift and respect changes made externally.
- No uncontrolled changes to Off-grid AC coupling, off-grid backup load toggle, mode 2 Backup or mode 3 Off-grid/Passive.
- Timed actions, power limits, minimum run/pause intervals, hysteresis and safe stop required for equipment.
- No assumption that OCPP, HVAC control or SAJ write access is presently available.
- Collect model/firmware, charger capabilities and electrical installation constraints before implementation. Avoid hardcoded values and unsafe "max" presets.

## Planned UI

A compact "Energy Automation" or "Smart Loads" section/tab, with:
- Battery: current SOC/kWh, mode, next TOU action, observed vs pending status.
- EV: plugged-in/charging state, requested amperes, actual charger power, target SOC/departure time if supported, solar-surplus mode.
- Air conditioning: enabled/paused/normal mode, temperatures and comfort constraints.
- Grid: imports, exports, maximum limits and source freshness.
- Owner overrides, priority selection, clear Cancel/Stop where safe, and external-change alerts.

Only display capabilities actually discovered on installed devices. No fake controls.

## Implementation sequencing

This roadmap is **after** the near-term SAJ mode/TOU synchronization milestones. Do not let large-load ambitions accelerate unsafe Modbus writes or impair existing read-only monitoring.

**Cross-links:** [Developer Handoff](../DEVELOPER_HANDOFF.md), [SAJ App TOU observations](SAJ_APP_TOU_OBSERVATIONS.md), [Telemetry Contract](TELEMETRY_CONTRACT.md), [Safety/Roadmap](SAFETY_AND_ROADMAP.md).
