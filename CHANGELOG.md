# Changelog — SAJ H2 Control Enhanced

## 0.2.0 — 2026-11-01 (dynamic TOU dashboard and discovered monitor setup)

**Released in GitHub only; not installed on the owner's Kamrui yet. All editor controls are preview-only.**

- Created `custom_components/saj_h2_control_enhanced/frontend/saj-tou-dynamic-card.js`: dark-theme-compatible card that **discovers configured TOU devices and their renamed entities** through explicit `saj_tou_entry_id` and `saj_tou_role` attributes rather than fixed entity IDs.
- Shows current mode, non-scheduled fallback and live 0–7 charge/0–7 discharge schedules with 24-hour time inputs, seven weekday selections, percent/power sliders and dynamically added or removed draft slots.
- **No writes:** there is no Apply action, no HA service call and no Modbus write transport. Preview edits exist only in the browser session and remain clearly separate from inverter-saved state.
- Pristine drafts follow incoming official eLEKeeper/Modbus readback; edited drafts remain until the user explicitly reloads from the inverter.
- `config_flow.py` selects an already configured SAJ H2 Safe Monitor automatically at setup time; manual IP entry remains only as fallback. Existing installs retain their original config and entity unique IDs; coordinator may follow the uniquely matching Safe Monitor host/port.
- `frontend_setup.py` serves card JS from its bundled folder, adds a frontend resource and **attempts to create a separate SAJ TOU Control dashboard if absent**, without modifying any existing dashboard. Automatic dashboard creation is best effort; failures log and leave existing dashboards alone.
- Integration version bumped to **0.2.0**; preserved existing sensor unique IDs and read-only Modbus function 03 polling.
- Added JavaScript `node --check` to CI alongside the previous Python syntax, offline safety and no-Modbus-write tests.
- See [Dynamic dashboard v0.2.0 guide](docs/DYNAMIC_DASHBOARD_V020.md).

**Not yet verified:** Browser rendering/automatic dashboard creation against the owner's precise HA version. No physical inverter command testing; charge-side watt conversion and weekday bits except Wednesday remain unverified.

## 0.1.1 — 2026-11-01 (read-only TOU synchronization improvements)

- Compare **both entire schedule register blocks twice** during a single poll, not just mode and enable masks. A schedule changed by eLEKeeper while being read will be discarded and retried at the next poll.
- Track **active settings changes** separately from stale values in disabled slots. Avoid false alerts when unused memory contains old schedules.
- Record `last_device_change`, `last_changes`, and the running count of changed configurations as Home Assistant attributes. All changes are observations, not commands issued by HA.
- Add a conservative weekday label: **Wednesday** verified for raw mask `4`; other day masks are shown as unverified rather than guessed.
- Add [compact read-only TOU dashboard card](examples/tou-compact-card.yaml) showing mode, fallback, 0–7/7 schedule counts, full active rows and synchronization state.
- Add regression tests for external setting changes, inactive-slot noise, confirmed weekday decoding and observed raw power mapping.
- GitHub Actions: syntax and offline safety checks passed on the repaired code.
- Existing `saj_h2_safe` integration and SAJ Energy dashboard are **unchanged**. The new code is **not auto-installed** in Home Assistant.

**No new writable services or Modbus write methods. No change to battery/solar behaviour.**

### Updating the owner's existing 0.1.0 preview

When owner returns, copy **only** `custom_components/saj_h2_control_enhanced` from latest GitHub to the same directory on Kamrui and restart `homeassistant`. This is an in-place file upgrade: do **not** delete the integration entry or touch the separate `saj_h2_safe` directory. Existing entity IDs and their unique IDs have been preserved. Confirm the sync sensor's new `last_changes` and `last_device_change` attributes.

## 0.1.0 — 2026-11-01 (initial working field test)

- Owner successfully installed `saj_h2_control_enhanced` in HA.
- Separate `SAJ H2 TOU Readback` device created and returned mode `Time-of-use`, outside fallback `Self-consumption`, 0 enabled charge schedules, 1 enabled discharge schedule and readback OK.
- Schedule contents stored in sensor attributes; Wednesday 22:00–22:40 and 4950 W after the app-saved 5000 W request were established by raw Modbus readback and official eLEKeeper observation.
- Read-only Modbus function 03 and 120 s default refresh; no control/automation write functions.

## Future gates

1. Confirm live schedule attributes in HA match eLEKeeper after an externally initiated change, including no cache/rename mismatch.
2. Obtain independent readback evidence for charge power conversion and other weekday masks.
3. Expand reliable sensor continuity and safe debug diagnostics.
4. Only after model/firmware-specific verification, safe-stop proof and owner authorization consider any writable control experiments. Never command mode 2 Backup or 3 Off-grid/Passive.
