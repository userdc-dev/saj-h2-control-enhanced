# SAJ H2 Control Enhanced — Home Assistant

**Independent, actively developed battery controller for SAJ H2 with live operating mode, editable TOU schedules, outside-window fallback, and an optional read-only energy overview.**

> **New developer / AI assistant:** [READ THE COMPLETE DEVELOPER_HANDOFF.md FIRST](DEVELOPER_HANDOFF.md). The handover includes exact inverter registers, code architecture, real-vs-simulated testing evidence, safety gates, recovery steps, and outstanding requirements. The historical chronology is preserved in [the archive](docs/DEVELOPER_HANDOFF_HISTORY_THROUGH_V040.md).
>
> **Version in this README:** v0.5.10. Inspect [manifest.json](custom_components/saj_h2_control_enhanced/manifest.json) and [GitHub Actions](https://github.com/userdc-dev/saj-h2-control-enhanced/actions) to confirm the current release.

**Versioning rule:** Keep iterative improvements in the pre-1.0 patch series (`0.5.6`, `0.5.7`, etc.) until the complete feature set is stable and hardware-verified. Reserve **v1.0.0** for the final release; do not prematurely claim stability with a major version bump.

## What this integration does

- Controls operating mode: **Self-consumption ↔ Time-of-Use**. Both directions have been verified on the owner's actual SAJ H2-10K-S3-A inverter and in elekeeper.
- Edits **up to seven charge** and **seven discharge** time slots, with 24-hour time pickers, Monday–Sunday day choices, add/remove, and a power slider showing **both percentage and estimated watts**.
- Uses **Save schedule changes to inverter** with internal validation and **one confirmation popup**; each changed Modbus word is verified. Multiple writes are not atomic; an interruption could leave partial settings.
- Supports **Outside TOU windows: Self-consumption or Standby** through a dark, accessible in-card menu (avoiding white native popup on Windows/Brave). Selecting Standby displays one warning popup. The new fallback write has been offline-tested but has **not** been independently verified in a completed field test.
- Offers **Split overnight into two schedules** in the UI because elekeeper does not support a single schedule crossing midnight.
- Includes a polished **Live energy flow** inside the TOU dashboard, based on existing read-only SAJ Safe Monitor entities: Solar, House, Battery, Grid and Forecast table; relative power bars; battery SOC and estimated stored energy. This visualization is read-only and must not modify the monitoring integration.
- Provides a **Refresh / reload data** action next to Last verified; it requests fresh read-only TOU settings, Safe Monitor live data and forecast data without any Modbus writes. The **Inverter controls** header shows both actual live settings (Operating + Outside TOU). Charging and discharging cards use compact headers with Add actions, and warnings appear only where needed. Auto-creates a **separate SAJ TOU Control** sidebar dashboard with the native page title **SAJ H2 Control**. Existing integration-generated dashboards receive a safe title-only migration; customized dashboard layouts are never overwritten. With multiple inverters, the device switcher appears immediately below the native Home Assistant header.

The integration is **not** a completed universal inverter controller: forced timed charging/discharging, OCPP, HVAC, and automatic tariff optimisation remain future work. Inferred Saturday/Sunday individual bits and some schedule-write combinations still need additional field verification.

## Non-negotiable boundaries

- Do not modify the separate [SAJ H2 Safe Enhanced](https://github.com/userdc-dev/saj-h2-safe-enhanced) monitor or the owner's existing **SAJ Energy** dashboard.
- Modbus operating modes **2** (Backup) and **3** (Off-grid/Passive) remain blocked. No writing battery protections, reserve SOC, inverter export limits, off-grid settings, or BMS registers.
- No startup/background/automated writes. Always require an explicit user action. Standby must have a clear confirmation popup.
- Do not automatically retry or rollback an uncertain/partially committed multi-register write.
- Actual on-device verification is different from fake-Modbus CI passing. See the [evidence matrix](DEVELOPER_HANDOFF.md#3-implementation-status-what-is-genuinely-verified).

## Architecture

| Component | Purpose |
|---|---|
| `custom_components/saj_h2_control_enhanced/__init__.py` | HA setup, read coordinator, user-invoked actions and shared write lock |
| `tou_protocol.py` | 7+7 slot register decoder and current mode/fallback |
| `schedule_transaction.py` | Full schedule plan, preflight, changed-register application and verification |
| `supervised_write.py` | Single-mode writes (0 ↔ 1) |
| `supervised_fallback.py` | Outside-TOU Self-consumption / Standby write with confirmation |
| `frontend/saj-tou-dynamic-card.js` | Time-of-use control UI plus read-only live energy graphics and table |
| `frontend_setup.py` | Versioned frontend resource and independent dashboard |
| `sensor.py` | Device readback sensors; never speculative setting states |

Core TOU registers: charge mask `0x3604`, discharge mask `0x3605`, charge slots `0x3606–0x361A`, discharge slots `0x361B–0x362F`, mode `0x3647`, outside fallback `0x365F`. See the [full handover](DEVELOPER_HANDOFF.md#4-authoritative-modbus-tou-layout-and-encodings) for bytes, masks, examples and provenance.

## Installation from GitHub — no YAML changes

**Complete step-by-step guide:** [docs/INSTALLATION.md](docs/INSTALLATION.md).

The repository includes the config-flow setup, all Python code, bundled JavaScript card, automatic dashboard creation and a [`hacs.json`](hacs.json) manifest. **You do not edit `configuration.yaml`, Lovelace YAML or JavaScript resources.**

**UI installation:** In HACS / Home Assistant Marketplace (as supported by your version), add this GitHub URL as a **custom Integration repository**, install and restart HA. Then use **Settings → Devices & services → Add integration → SAJ H2 Control Enhanced**. Select an existing Safe Monitor entry or enter the SAJ inverter's Modbus IP and port. The **SAJ TOU Control** sidebar and **SAJ H2 Control** dashboard are created automatically. If only one inverter is configured the card hides the device selector; multiple configured inverters get a chooser.

**Command-line installation or update:** From a downloaded/checked-out copy of this GitHub repository, run:

~~~bash
bash scripts/install.sh /path/to/homeassistant/config
~~~

To additionally install the independent **SAJ H2 Safe Enhanced** read-only component **only when missing**, run:

~~~bash
bash scripts/install.sh /path/to/homeassistant/config --with-safe-monitor
~~~

The optional safe monitor provides Live energy/forecast sensors; **it is separate by design** and is never overwritten by the installer. Restart HA normally and complete its config flow separately. An existing monitor continues working untouched. The script backs up existing TOU integration code outside `custom_components/`, so HA does not see duplicate integration folders. Backing up code **does not undo inverter schedule/mode changes**. A downloadable branch archive from `main` can change over time; review a release commit when reproducibility matters.

For HA OS installations without direct access to the configuration filesystem, use HACS / Marketplace. See [docs/INSTALLATION.md](docs/INSTALLATION.md) for screenshots/navigation, first-run checks, and troubleshooting.

## Testing and evidence

GitHub CI runs syntax checks and simulated Modbus unit tests. Readable verification notes in [docs/SAJ_APP_TOU_OBSERVATIONS.md](docs/SAJ_APP_TOU_OBSERVATIONS.md) trace real elekeeper pairing tests. The current [developer handover](DEVELOPER_HANDOFF.md) distinguishes verified live mode switching from schedule/fallback paths that remain only partially field-proven. No CI test connects to the physical inverter.

Quick offline checks:

~~~bash
python -m compileall -q control_core custom_components tests
node --check custom_components/saj_h2_control_enhanced/frontend/saj-tou-dynamic-card.js
python -m unittest discover -s tests -p 'test_schedule_transaction.py'
python -m unittest discover -s tests -p 'test_supervised_fallback.py'
~~~

## Continuing development

Start with [DEVELOPER_HANDOFF.md](DEVELOPER_HANDOFF.md), then the source files named above. Preserve the one-confirmation UX and lowercase **elekeeper** branding, never overwrite the safe monitor, and record actual hardware results separately from offline simulations. Update the handover and changelog with every important change.
