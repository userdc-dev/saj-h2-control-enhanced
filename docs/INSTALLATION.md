# Installation and upgrades — one repository, no YAML

Everything needed is hosted in **this GitHub repository**: the SAJ H2 Control Enhanced integration, its dynamic dashboard/card and a bundled copy of the read-only SAJ H2 Safe Monitor (Live energy, battery, grid, consumption and forecast). **No second repository** is needed.

The original monitor remains its own Home Assistant integration domain (`saj_h2_safe`) to **preserve existing entity identities, config entries, dashboard references and historical data**. Keeping that domain is an internal compatibility detail, not an external download requirement.

## v0.5.19 solar forecast learning

Solar forecast now includes **Forecast learning & accuracy**. After updating, Home Assistant may scan its **existing hourly long-term statistics** automatically and approximately weekly. You can also choose a **30-day, 90-day, six-month or twelve-month history window** and select **Analyse past readings**. This calibrates read-only forecasts only; it does not adjust the inverter or affect existing schedules, cost settings, Historic Data or Energy sensors.

*Availability matters:* Home Assistant can't reconstruct months before the SAJ solar and battery SOC sensors started recording. A recently installed monitor may initially report no qualifying history. Previous-day forecast accuracy begins accumulating **from the time v0.5.19 starts saving genuine forecasts**, not retroactively. For details and backtest limitations see [Solar forecast learning](SOLAR_FORECAST_LEARNING.md).

## 1. Easiest installation: one copy/paste block (Linux / Docker)

SSH into the machine running Home Assistant, **replace `/home/USER/compose-files/homeassistant/config` with your real Home Assistant configuration directory**, then run:

```bash
curl -fL https://raw.githubusercontent.com/userdc-dev/saj-h2-control-enhanced/main/scripts/install.sh -o /tmp/install-saj-h2.sh &&
bash /tmp/install-saj-h2.sh /home/USER/compose-files/homeassistant/config &&
docker restart homeassistant
```

`USER` is a placeholder (not a literal or automatically discovered username). Docker configuration mounts differ: some installations do not use `compose-files/homeassistant/config` at all. Verify your config directory and change the full path if needed; also replace `homeassistant` with your actual Docker container name. For the original Kamrui host, the known working directory is `/home/kamrui/compose-files/homeassistant/config`. Home Assistant OS users should **not** run this Docker-specific command.

The installer:

1. Downloads the archive of **this repository only**.
2. Installs/upgrades the controller from `custom_components/saj_h2_control_enhanced`.
3. Installs the bundled `saj_h2_safe` monitoring integration **only if missing**. An existing monitor is **never overwritten**.
4. Creates a timestamped controller code backup in `.saj-h2-backups/` within the HA config directory before an upgrade.
5. Leaves `configuration.yaml`, existing dashboard layouts, saved config entries and inverter settings unchanged.

**No `--with-safe-monitor` flag is needed or supported.** The monitor is bundled by default. Optional advanced usage: `bash /tmp/install-saj-h2.sh /path/to/config --control-only` intentionally skips monitoring.

## 2. Complete setup in Home Assistant

After Home Assistant restarts:

1. Open **Settings → Devices & services → Add integration**.
2. Search **SAJ H2 Safe Monitor**. If you do not already have it configured, add it with the inverter's Modbus TCP IP and port **502**. An existing configuration should be reused, not deleted.
3. Search **SAJ H2 Control Enhanced**. Select the existing Safe Monitor entry (preferred), or manually enter the *same* inverter IP and port. Configure the integration.
4. Open the auto-created **SAJ TOU Control** sidebar dashboard (page title **SAJ H2 Control**).
5. Check **Last verified**, read-only Live energy readings and current operating mode. Draft a schedule without saving to test UI controls. **Do not perform a live write simply to test installation.**

**Important:** This is one GitHub repo / one script, but currently **two HA configuration entries**. They retain separate domains to avoid breaking previous data and automations. The control component does not change the read-only monitor's code or your original SAJ Energy dashboard.

## 3. HACS / Marketplace option

The repository contains a root `hacs.json` and supports installing **SAJ H2 Control Enhanced** as a HACS custom Integration repository:

`https://github.com/userdc-dev/saj-h2-control-enhanced`

Install and restart, then configure the controller in Settings → Devices & services.

**Limit:** HACS installs the controller folder; it does **not** automatically install the additional `bundled_components/saj_h2_safe` directory. If the read-only monitor is already installed, it is reused. Otherwise, use the installer in section 1 for the **full** installation. You never need to visit or clone another GitHub repository. On Home Assistant OS without host shell/config access, use an appropriate supported file-management installation method to install the bundled monitor; HACS alone will not provide new Live energy sensors.

## 4. Built-in Energy, electricity prices and smarter forecasts

After configuring **both** integrations, your SAJ H2 Control dashboard now has **Energy & controls**, **Costs & savings** and **Solar forecast** tabs.

The Costs & savings tab includes a **full time-of-use rate editor**, supporting multiple import windows, weekend/weekday selections, standard and high export FiT windows, signed prices, and GST/extra levies. Follow the [Tariff setup guide](TIME_OF_USE_TARIFFS.md); every example value must be replaced with your actual retailer plan.

- In **Costs & savings**, configure your Peak/Off-peak/Solar sponge time windows, standard and special FiT periods, signed prices, daily supply and GST/other tax settings. Default prices are illustrative and not applied as real prices until confirmed.
- In **Settings → Dashboards → Energy**, select the new human-readable sensor aliases for solar, grid and battery using the [Energy & Costs setup guide](ENERGY_AND_COSTS.md). Grid-energy totals are estimates from recorded signed power; verify polarity with a known import/export condition before using them.
- The editable solar forecast learns gradually from qualified clear-sky hours; the read-only SAJ monitor and your original SAJ Energy dashboard are unchanged.
- If you configure Safe Monitor **after** the controller was already loaded, reload SAJ H2 Control Enhanced so it can attach its optional read-only energy accounting.

## 5. Check the result

| What to check | Expected |
|---|---|
| Integration dashboard | Sidebar **SAJ TOU Control**; page **SAJ H2 Control** |
| TOU settings | Current operating mode, outside-window fallback, charging/discharging schedules, readback timestamp |
| Live energy | Solar, House, Battery, Grid and Forecast when the bundled monitor is **configured and reporting** |
| Existing HA data | Old entities and dashboards remain; upgrades never remove saved config entries |
| Safety | No automatic Modbus writes; user actions require validation and confirmation |

Unavailable monitor sensors must display unavailable values, never fabricated zero readings. If readings are missing, confirm the Safe Monitor integration is configured, its Modbus IP is correct and it reports available entities. The dashboard reads those existing entities.

## 6. Upgrades and troubleshooting

### v0.5.26: intermittent dashboard Configuration error, including Android

This version registers the bundled card as a Lovelace **module resource**, rather
than relying solely on global extra JavaScript loading. This addresses a potential
card-registration race on cold loads. Rendering failures now show a local retry
message and recover on the next state update or view attachment. Unsaved drafts
stay in memory, and partial control buttons are removed while rendering has failed.
No automatic inverter commands are added.

1. Once v0.5.26 is merged/released, update using HACS or the existing installer
   above. The installer downloads `main`; it does **not** install an unmerged PR.
   To test the PR before merge, download its branch ZIP from GitHub and replace
   only `custom_components/saj_h2_control_enhanced` in your HA config directory,
   keeping a copy of the previous folder. Leave the monitor and config files alone.
2. Restart Home Assistant. Confirm the integration version is **0.5.26**.
3. In storage resource mode, the integration creates/updates only its own
   `/saj-h2-tou/v…/saj-tou-dynamic-card.js` module resource automatically. It does
   not replace dashboard layouts or unrelated resources. The new URL is
   `/saj-h2-tou/v0526/saj-tou-dynamic-card.js`.
4. If you manage Lovelace resources in YAML, update/add that URL with
   `type: module` in your existing resource list yourself; this version never
   rewrites YAML. A warning in HA logs identifies this case.
5. Fully close and reopen the Android app. If it still shows the old card, use
   the companion app's frontend cache reset/refresh option if available, then
   reopen the dashboard. A frontend reload is needed because custom elements
   cannot be replaced in an already-open browser session.
6. Check opening the dashboard fresh, backgrounding/resuming the app, and moving
   between tabs. Confirm live data returns without pressing any inverter actions.

If it persists, capture a screenshot (including any expanded error text), the
time, HA Core and Android System WebView versions, and HA logs containing
`frontend_setup`, `saj_h2_control_enhanced`, or `Custom element doesn't exist`.
A browser console stack starting `SAJ card rendering failed` is particularly
useful. Remove tokens, addresses and serial numbers before sharing. The automated
tests use a mocked DOM and HA resources; actual Android/WebView verification is
still required. To roll back, restore the backed-up controller folder and restart
HA, then fully reopen the app; the integration will restore its versioned resource.

- **Update using the same installation command** as section 1. Existing controller files are backed up. Existing `saj_h2_safe` files are preserved unchanged, including locally customized versions.
- **Old UI:** restart Home Assistant and hard-refresh the browser. Inspect the versioned frontend asset and HA logs if necessary.
- **Missing dashboard:** ensure the controller config flow completed; inspect the Home Assistant logs for dashboard setup errors.
- **Unavailable Live energy:** configure/verify `saj_h2_safe`, which is already supplied by this repo's installer. The TOU controls do not depend on energy sensors being available.
- **Write blocked:** check stale readback, active drafts, profile mismatch or a busy write lock. Start with read-only Refresh.
- **Ambiguous or partial schedule write:** do **not** retry blindly; re-read device state and compare with elekeeper first.

### Compatibility and safety

Supported live-write profile is the field-tested SAJ **H2-10K-S3-A / firmware v2.018**. Other models/firmware are blocked for writes until verified. Read-only data and test simulations do not prove a safe live write. Modes 2/3, BMS protections, reserve SOC, off-grid settings and export limits remain blocked. No startup, polling or scheduled Modbus writes. Multi-word schedule changes are not atomic; a failed write may have applied partly. Backing up integration code **does not undo changes made to the inverter**.

For engineering and hardware-test detail, read [DEVELOPER_HANDOFF.md](../DEVELOPER_HANDOFF.md).
