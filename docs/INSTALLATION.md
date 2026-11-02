# SAJ H2 Control Enhanced — easy installation

**Everything needed for the complete dashboard is supplied by this GitHub repository.** This includes the inverter controls, the read-only Safe Monitor (solar, home, battery, grid and forecast), the JavaScript card, and the automatic Home Assistant dashboard.

You do **not** need to visit another repository, download separate dependencies, or edit `configuration.yaml`, Lovelace YAML, or dashboard JavaScript resources.

## Quick install — copy and paste (recommended)

For a Home Assistant Docker installation on Linux, open SSH/Terminal and run:

```bash
curl -fL https://raw.githubusercontent.com/userdc-dev/saj-h2-control-enhanced/main/scripts/install.sh -o /tmp/install-saj-h2.sh &&
bash /tmp/install-saj-h2.sh /home/kamrui/compose-files/homeassistant/config &&
docker restart homeassistant
```

**This command is for the existing Kamrui installation.** On another machine, replace `/home/kamrui/compose-files/homeassistant/config` with **that machine's own Home Assistant config folder**. If Home Assistant is not running as a Docker container named `homeassistant`, restart it using its normal service or UI rather than the last `docker restart` command.

For any other Linux/Docker installation, the generic steps are:

```bash
curl -fL https://raw.githubusercontent.com/userdc-dev/saj-h2-control-enhanced/main/scripts/install.sh -o /tmp/install-saj-h2.sh
bash /tmp/install-saj-h2.sh /path/to/your/homeassistant/config
# Restart Home Assistant using your usual method
```

The script fetches **one archive of this repository** and installs:

| Component | Included in this repo | Purpose |
|---|---|---|
| `custom_components/saj_h2_control_enhanced/` | Yes | TOU readback, mode/schedule/fallback controls, and complete auto-created dashboard |
| `bundled_components/saj_h2_safe/` | Yes | Independent **read-only** solar, battery, grid and forecast monitoring |

During installation the bundled monitor is copied into Home Assistant's `custom_components/saj_h2_safe/` folder **only if that folder does not already exist**. Any existing Safe Monitor is deliberately preserved **unchanged**, including its configuration, entities and dashboards. Existing controller code is backed up under `<config>/.saj-h2-backups/` before an upgrade.

### First-time setup after the restart

Open **Home Assistant → Settings → Devices & services → Add integration**:

1. Search for **SAJ H2 Safe Monitor**, select it, and enter your SAJ inverter's Modbus **IP address** and port (**502**, unless your device uses another port). If the Safe Monitor was already configured, **skip this step**.
2. Search for **SAJ H2 Control Enhanced**. Choose the existing Safe Monitor as its source, or enter the same inverter IP/port manually. If the controller was already configured, **skip this step** too.
3. Open **SAJ TOU Control** from the left sidebar. The page is titled **SAJ H2 Control**. It contains Live energy, operating/outside-TOU controls, and charging/discharging schedules.

**That's it.** The integration registers its own JavaScript card and creates its own dashboard. There are no YAML, manual JS resource or dashboard-card setup steps.

The inverter must support local Modbus TCP, and Home Assistant must be able to reach its IP address. The actual hardware/firmware profile and safety restrictions are documented in [the developer handover](../DEVELOPER_HANDOFF.md). No inverter write occurs during installation or initial readback.

## Updates — the same simple command

Run the **same three-line command** above. It updates the controller, preserves the existing monitor, and restarts Home Assistant.

The GitHub `main` branch changes over time. For a controlled deployment, review the [repository history](../CHANGELOG.md) and installer before running a new release. Backing up the controller's code **does not** restore settings that were already written to the inverter.

To deliberately install **only the controller** without copying the bundled monitor:

```bash
bash /tmp/install-saj-h2.sh /path/to/your/homeassistant/config --control-only
```

That is optional. The **default**, with no flag, is the **complete installation**.

## Home Assistant OS or installations without SSH

If your Home Assistant installation does not expose the config folder to a Linux shell, you can use its supported File editor / Samba / add-on to copy these **two folders from this same repository** to `config/custom_components/`:

- `custom_components/saj_h2_control_enhanced/`
- `bundled_components/saj_h2_safe/` (copy the folder as `custom_components/saj_h2_safe/`; skip it if you already have a Safe Monitor)

Restart HA and complete the **First-time setup** steps above. No YAML is required.

**HACS / Marketplace note:** HACS custom repository installation can install the controller integration from this repository. HACS generally installs one integration directory, so **HACS alone is not the full two-component installation** for new users. For the complete Live energy dashboard, use the single-repository command above, or copy the already-bundled monitor folder from this repository. **No other source repository is needed.**

## Troubleshooting

| Symptom | What to check |
|---|---|
| No new sidebar dashboard | Finish the **SAJ H2 Control Enhanced** config flow in **Settings → Devices & services**; restart HA and check logs for `async_ensure_dashboard` |
| Live energy missing | Confirm **SAJ H2 Safe Monitor** appears in HA Devices & services and its sensor states are available. Its code is already bundled in this repository |
| The inverter isn't found | Confirm its local IP, port 502 (or your configured port), and reachability from the HA machine |
| Changes look stale | Use **Refresh / reload data** beside Last verified, then reload the browser |
| New version looks like old UI | Restart HA and hard-refresh the browser; frontend URL is versioned in `frontend_setup.py` |
| Save button disabled | Make a schedule edit, check device mode is supported and sensor readback is fresh |
| Unexpected inverter setting after interrupted Save | **Do not blindly retry.** Read all settings from the inverter and elekeeper first; schedule writes are not atomic |
| Existing Safe Monitor | The script skips it rather than replacing, resetting or deleting any monitoring data |

## Safety and limitations

The code has an explicit **read-only monitoring** component and a separate **user-controlled write** component. Installing either does not trigger a write. Modbus mode 2/3, BMS protections, grid limits and backup/off-grid functions are not exposed for writing. Some schedule/fallback write combinations still need live hardware verification; GitHub CI tests use simulated Modbus and do **not** certify other inverter models or firmware.

For developers, read [DEVELOPER_HANDOFF.md](../DEVELOPER_HANDOFF.md), [README.md](../README.md), [CHANGELOG.md](../CHANGELOG.md), and the [offline tests](../tests/). Everything needed to install this project now comes from **this repository**.
