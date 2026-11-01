# Installation and upgrades — no YAML required

This repository contains the **complete SAJ H2 TOU Control integration and bundled dashboard card**. Do **not** edit `configuration.yaml`, add a Lovelace YAML card, or manually register any JavaScript. The integration automatically serves its card and creates a separate sidebar dashboard **SAJ TOU Control** with the Home Assistant page title **SAJ H2 Control**.

## Requirements and important separation

- Home Assistant with a working network connection to the SAJ H2 inverter's **Modbus TCP** endpoint (typically port **502**, slave/device ID **1**).
- Tested hardware profile in this project: **H2-10K-S3-A** with control firmware **v2.018**. Control writes on other firmware/models are **blocked by design** until verified.
- For the **Live energy** panel (Solar, House, Battery, Grid, Forecast), separately install the **read-only** [SAJ H2 Safe Enhanced](https://github.com/userdc-dev/saj-h2-safe-enhanced) integration. The TOU integration can work without it, but the energy overview will show unavailable measurements. The safety monitor is not bundled inside this one-integration repository and must remain independent.
- The installer does **not** enable or execute Modbus writes. Commands require explicit user interaction and confirmation in the dashboard.

## Option A — install through HACS / Home Assistant Marketplace

The repo includes `hacs.json`, `manifest.json`, a single `custom_components/saj_h2_control_enhanced/` directory, bundled frontend JS, config flow, and readback sensor definitions.

1. In **HACS / Marketplace**, open **Custom repositories** (if supported by your Home Assistant version) and add `https://github.com/userdc-dev/saj-h2-control-enhanced` as **Integration**.
2. Install **SAJ H2 Control Enhanced** and **restart Home Assistant**.
3. Open **Settings → Devices & services → Add integration** and search for **SAJ H2 Control Enhanced**. Choose an existing **SAJ H2 Safe Monitor** entry if present, or use the **Manual IP address** option and enter the inverter's Modbus host/port.
4. Home Assistant creates the sidebar **SAJ TOU Control** automatically. Open it; no manual Lovelace YAML, JavaScript resource registration, or view creation is needed.
5. For the full Live energy overview, similarly install the separate [SAJ H2 Safe Enhanced](https://github.com/userdc-dev/saj-h2-safe-enhanced) repository if it is not installed already; configure it through its own HA integration setup using the **same inverter IP**. Do not delete or overwrite existing Safe Monitor entries.

HACS / Marketplace navigation and custom repository availability vary by HA version. If your client does not support custom repositories, use Option B. Changes in HA dashboard storage APIs may affect automatic creation; inspect HA logs rather than editing arbitrary Lovelace storage files.

## Option B — one script from GitHub on Linux/Docker installations

The repository contains `scripts/install.sh` for users with shell access to their Home Assistant **configuration directory**. It takes the configuration directory as an argument rather than assuming any IP, username or machine layout.

```bash
# From a clone/download of this repository:
bash scripts/install.sh /path/to/homeassistant/config
```

To install the **independent Safe Monitor only if it is missing**, so that Live energy can work:

```bash
bash scripts/install.sh /path/to/homeassistant/config --with-safe-monitor
```

The optional Safe Monitor flag **never overwrites an existing Safe Monitor**. The script backs up an existing SAJ TOU code directory under `<HA_CONFIG>/.saj-h2-backups/`, checks the downloaded manifest, and copies the integration files into `custom_components/`.

It downloads the current `main` branch, which is **not pinned**. For controlled deployments, review the tagged release / commit before installing. The script does not restart HA, modify YAML, delete HA entities, revoke third-party control, or change saved inverter schedules. **Restart Home Assistant using its normal process**, then add each integration through **Settings → Devices & services**. A restarted integration with an existing config entry should resume automatically.

The script needs `curl`, `tar`, `mktemp` and standard shell utilities. For HA OS without shell access to its mounted configuration directory, use HACS/Marketplace or the supported file-management method instead.

## Verify your installation

- Sidebar **SAJ TOU Control** opens **SAJ H2 Control** with a green connected status and a **Last verified** timestamp.
- The bundled frontend shows **Live energy**, operating and outside-TOU settings, and charging/discharging periods. If Safe Monitor has not been installed/configured, Live energy readings may be unavailable; TOU controls can still work.
- Mode and fallback should reflect **actual device readback**. Data is automatically polled; the **Refresh / reload data** button near Last verified requests another read without changing inverter settings.
- Try **adding a draft schedule without saving** and confirm that it is marked unsaved. Do not perform an actual schedule write just to check that the dashboard installed.
- Check the system logs and GitHub Actions if frontend layout/JS fail to load. Cache-busting version is in `custom_components/saj_h2_control_enhanced/frontend_setup.py`.

## Upgrade without losing state

- HACS / Marketplace: update the integration and restart HA. Reload browser resources if necessary.
- Script: rerun it with the same HA config path, preserving the same existing HA config entry and sidebar. The script saves a **code backup**; that backup **does not revert inverter settings already written**.
- The integration never requires a custom YAML change when adding a new dashboard release. If you manually customized the generated dashboard, the integration intentionally avoids overwriting your changes.
- For multi-inverter setups, the frontend displays a device chooser immediately below the HA navigation bar. Use the actual device in the selector before sending commands.

## Troubleshooting

| Problem | First safe action |
|---|---|
| No sidebar/dashboard after adding integration | Confirm config flow completed and integration is loaded; inspect HA logs for `async_ensure_dashboard`; no custom YAML is normally needed |
| Blank custom card or old UI | Restart HA, hard-refresh browser, check versioned JS URL in `frontend_setup.py` |
| No Live energy readings | Install/configure **separate read-only Safe Monitor**; check that its entities have available states |
| Can't change mode | Freshness or unsupported current mode, pending draft, or write lock; use read-only Refresh |
| Schedule Save unavailable | Make a local edit first and ensure current device mode is supported |
| Partial/ambiguous write | **Do not retry.** Read all slots/mode/fallback from inverter and elekeeper first; multi-register updates are not atomic |
| Native dark dropdown inconsistent | Current frontend provides a dark in-card Outside TOU menu; verify the browser is loading the latest versioned script |

## Security and hardware boundaries

The Home Assistant dashboard is not a substitute for physical inverter safety protections. Mode 2/3, BMS, SOC reserve, backup/off-grid switching, export limits, and other sensitive settings are not writable through this repo. Only confirmed firmware/hardware profiles may reach user-triggered Modbus write services. The old third-party/VPP control status shown in elekeeper may indicate a competing controller. **No blind retries** on unknown write outcomes.

See [complete developer handover](../DEVELOPER_HANDOFF.md), [paired elekeeper readback evidence](SAJ_APP_TOU_OBSERVATIONS.md), and [CI workflow](../.github/workflows/safety-tests.yml).
