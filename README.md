# SAJ H2 Control Enhanced — Home Assistant

**One-repository Home Assistant package for SAJ H2 control and bundled read-only energy monitoring, including live operating mode, editable TOU schedules, outside-window fallback and energy overview.**

> **New developer / AI assistant:** [READ THE COMPLETE DEVELOPER_HANDOFF.md FIRST](DEVELOPER_HANDOFF.md). The handover includes exact inverter registers, code architecture, real-vs-simulated testing evidence, safety gates, recovery steps, and outstanding requirements. The historical chronology is preserved in [the archive](docs/DEVELOPER_HANDOFF_HISTORY_THROUGH_V040.md).
>
> **Version in this README:** v0.5.19. Inspect [manifest.json](custom_components/saj_h2_control_enhanced/manifest.json) and [GitHub Actions](https://github.com/userdc-dev/saj-h2-control-enhanced/actions) to confirm the current release.

**Versioning rule:** Keep iterative improvements in the pre-1.0 patch series (`0.5.6`, `0.5.7`, etc.) until the complete feature set is stable and hardware-verified. Reserve **v1.0.0** for the final release; do not prematurely claim stability with a major version bump.

## What this integration does

- **Validated historical solar forecast learning (v0.5.19):** examines up to 30/90/180/365 days of **existing Home Assistant hourly long-term statistics**, aligns them to historical Open-Meteo tilted-radiation observations, learns seasonal/time-of-day calibration with a **chronological holdout**, and applies adjustments **only if the holdout MAE improves**. Also records fresh next-day forecasts **before** the target day and tracks forward daytime MAE and 5-day-over-5-day indicative trends. Shows real data coverage; does not invent unavailable historical readings or old issued forecasts. Calibration can be rerun from the forecast dashboard; initial and weekly checks are automatic. [Full forecast learning guide](docs/SOLAR_FORECAST_LEARNING.md).
- **Clutter-free dashboard (v0.5.18):** streamlined Costs & savings overview with collapsible detailed cost breakdown and time-of-use tariff editor; a four-column-responsive, initially collapsed **Home Assistant Energy sensor guide** shows actual entity IDs and friendly names in selectable inputs with Copy buttons (grid, solar, battery charge/discharge, SOC and home).
- **Every graph is inspectable:** the original Historic Data kW graph retains its hover/tap/keyboard crosshair. The forecast **Actual vs projected** kWh graph now offers the same inspection, plus separate daily/hourly forecast bars respond to hover/tap/focus. The actual forecast chart retrieves its **own local-day Recorder history**, flags missing observations, and visibly breaks lines across gaps. The 24-hour bar list and saved panel editor are collapsed by default to stay tidy.
- **Regression coverage:** Node's offline mock Home Assistant/DOM smoke test exercises copyable IDs, compact sections and forecast hover event handlers, alongside existing Python/JS safety and accounting tests. This is not a live browser hardware test.
- **Home Assistant Energy power management:** offers three clearly identified W/measurement sensor aliases: signed grid power for **Standard**, separate positive imported and exported power for **Two sensors**. Energy kWh sensor aliases remain separate and existing IDs are preserved. See [Energy integration guide](docs/ENERGY_AND_COSTS.md).
- **Fixed supply charge correction:** uses the **full user-configured daily supply fee per tracked local calendar day**, independently of partial sensor coverage; prior current-day prorated charges are reconciled during upgrade. No double-charging on a same-day tariff edit.
- Supplies **Home Assistant Energy-ready sensor aliases** for grid energy import/export estimates, lifetime solar production, battery charge/discharge, signed power, SOC and home consumption. Grid kWh estimates use monitored power data and require direction verification; don't mistake them for utility meters.
- Adds a **Costs & savings** dashboard tab and a compact Cost estimates summary, with editable signed **time-of-use import bands** (multiple morning/evening/overnight windows, weekdays and optional extra categories), standard/high export FiT schedules, separate fallback prices, optional GST/levies or rebates, and accrued today/month partial-coverage estimates. Negative feed-in tariffs and being paid to import are supported; live AEMO pricing is not yet active.
- Improves the user-editable **Solar forecast** with persistent, bounded learning from reliably observed clear-sky solar production hours, while skipping likely curtailment and uncertain data.
- Controls operating mode: **Self-consumption ↔ Time-of-Use**. Both directions have been verified on the owner's actual SAJ H2-10K-S3-A inverter and in elekeeper.
- Edits **up to seven charge** and **seven discharge** time slots, with 24-hour time pickers, Monday–Sunday day choices, add/remove, and a power slider showing **both percentage and estimated watts**.
- Uses **Save schedule changes to inverter** with internal validation and **one confirmation popup**; each changed Modbus word is verified. Multiple writes are not atomic; an interruption could leave partial settings.
- Supports **Outside TOU windows: Self-consumption or Standby** through a dark, accessible in-card menu (avoiding white native popup on Windows/Brave). Selecting Standby displays one warning popup. The new fallback write has been offline-tested but has **not** been independently verified in a completed field test.
- Offers **Split overnight into two schedules** in the UI because elekeeper does not support a single schedule crossing midnight.
- Provides a dedicated **Solar forecast** page within the existing dashboard, editable panel groups (count, watts, azimuth and tilt), system efficiency and reference AC inverter limit. Original 9/15/6 group values are defaults, with a first-use reminder to customize. Settings affect the forecast engine, not Modbus writes.
- Shows **Actual vs projected** solar generation and seven-day/hourly forecasts; adds four selectable **Home Assistant recorded-power** series below Live energy (Solar, House, Battery and Grid), with one clear kW scale, signed charge/discharge/import/export and hover/tap/keyboard inspection of nearby actual recorder values at 5/10/30-minute time steps.
- Includes a polished **Live energy flow** inside the TOU dashboard, based on the read-only SAJ Safe Monitor included in this repository: Solar, House, Battery, Grid and Forecast table; relative power bars; battery SOC and estimated stored energy. This visualization is read-only and must not modify the monitoring integration.
- Provides a **Refresh / reload data** action next to Last verified; it requests fresh read-only TOU settings, Safe Monitor live data and forecast data without any Modbus writes. The **Inverter controls** header shows both actual live settings (Operating + Outside TOU). Charging and discharging cards use compact headers with Add actions, and warnings appear only where needed. Auto-creates a **separate SAJ TOU Control** sidebar dashboard with the native page title **SAJ H2 Control**. Existing integration-generated dashboards receive a safe title-only migration; customized dashboard layouts are never overwritten. With multiple inverters, the device switcher appears immediately below the native Home Assistant header.

The integration is **not** a completed universal inverter controller: forced timed charging/discharging, OCPP, HVAC, and automatic tariff optimisation remain future work. Inferred Saturday/Sunday individual bits and some schedule-write combinations still need additional field verification.

## Non-negotiable boundaries

- Preserve an already installed `saj_h2_safe` monitor and the owner's existing **SAJ Energy** dashboard. The bundled monitor code is kept in this repository; do not overwrite an existing monitor during an upgrade.
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
| `bundled_components/saj_h2_safe/` | Bundled, independent read-only energy/forecast component installed from this repository |
| `scripts/install.sh` | One-repo installer for controller and missing monitor with no YAML changes |

Core TOU registers: charge mask `0x3604`, discharge mask `0x3605`, charge slots `0x3606–0x361A`, discharge slots `0x361B–0x362F`, mode `0x3647`, outside fallback `0x365F`. See the [full handover](DEVELOPER_HANDOFF.md#4-authoritative-modbus-tou-layout-and-encodings) for bytes, masks, examples and provenance.

## Install or update — one GitHub repository, no YAML

**Full beginner-friendly guide:** [Installation and upgrades](docs/INSTALLATION.md). [Historical solar forecasting and accuracy](docs/SOLAR_FORECAST_LEARNING.md). For selecting built-in HA Energy entities, editing signed tariff rates and understanding safe estimate limitations, see **[Energy & Costs guide](docs/ENERGY_AND_COSTS.md)** and **[Time-of-use tariff setup](docs/TIME_OF_USE_TARIFFS.md)**.

All required control code, the separate read-only monitoring *component*, the dashboard card and the installer are contained **in this repository**. You do **not** need to download a second GitHub repository, modify `configuration.yaml`, register a JavaScript resource or paste dashboard YAML.

### Recommended: one command (Linux / Docker host)

Run these commands in an SSH terminal on the Home Assistant host. **Before running:** replace `/home/USER/compose-files/homeassistant/config` with the actual Home Assistant config directory on your host (including your username/path). Replace `homeassistant` if your Docker container has another name. `/home/USER` is a placeholder, not an automatically detected path.

```bash
curl -fL https://raw.githubusercontent.com/userdc-dev/saj-h2-control-enhanced/main/scripts/install.sh -o /tmp/install-saj-h2.sh &&
bash /tmp/install-saj-h2.sh /home/USER/compose-files/homeassistant/config &&
docker restart homeassistant
```

**For the original Kamrui installation only:** substitute `/home/kamrui/compose-files/homeassistant/config` for the generic path above. This preserves the command that works for that host.

The installer downloads **only this repository**, installs/updates the controller, and also installs its **bundled read-only Safe Monitor if not already installed**. It preserves any pre-existing monitor directory instead of overwriting it, and backs up existing controller code. You do **not** need an extra `--with-safe-monitor` flag (that old documentation was incorrect).

After restart, go to **Settings → Devices & services → Add integration**. Configure **SAJ H2 Safe Monitor** (if not already configured) with your inverter IP and port 502; configure **SAJ H2 Control Enhanced** using that same monitor entry or its IP. These are two Home Assistant configuration entries, but **both are supplied by this single GitHub repository**. Existing configured entries remain in place on update. The controller creates the **SAJ TOU Control** sidebar dashboard automatically.

### HACS / Marketplace

You can add `https://github.com/userdc-dev/saj-h2-control-enhanced` as a custom **Integration** repository and install the controller through HACS, then restart Home Assistant. **Important limitation:** HACS normally installs only the directory `custom_components/saj_h2_control_enhanced`, not the repository's separately bundled `bundled_components/saj_h2_safe`. Thus, HACS alone is **not** presently the full two-component install on a new system. If you want the complete Live energy overview and do not already have Safe Monitor, use the one-command installer above instead; no other repository is needed. The TOU controls work without the monitor, while Live energy measurements will be unavailable.

For Home Assistant OS installations without host filesystem access, the controller can still be installed via HACS, but the full bundled monitor requires an accessible supported file-management/install route. We do not claim HACS automatically installs both components.

### Safety and updates

The installer itself sends **no Modbus writes** and never changes saved inverter schedules, Home Assistant entities, or dashboards. TOU writes still require explicit user interaction, preflight checking and readback verification. Restart HA after updating. An existing Safe Monitor's files are not overwritten; this preserves user modifications but can also mean an older monitor version remains installed. Script backups of code do **not** undo settings previously written to the inverter.

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
