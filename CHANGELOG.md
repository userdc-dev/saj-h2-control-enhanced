# Changelog — SAJ H2 Control Enhanced

## 0.5.7 — 2026-11-02 (compact energy, dark fallback popup, refresh near Last verified)

- Replaced the native Outside TOU dropdown, whose white Windows/Brave popup clashed with the dark theme, with a dark accessible in-card option menu. Preserved one confirmation for Standby and existing readback safeguards.
- Reordered Live energy into **Battery SOC → compact Solar/House/Battery/Grid power bars → condensed 5-column table**, matching the owner's reference screenshot. Reduced vertical space and duplicated status text; grid direction uses provisional sensor data rather than always “Import”.
- Added **⟳ Refresh / reload data** beside **Last verified**, explicitly requesting fresh read-only TOU, Safe Monitor live and forecast readings. Refresh targets one coordinator representative per source, not all sensor entities; it displays completion/error feedback beside the timestamp.
- Removed the redundant header refresh inside the inverter controls panel. No inverter write paths or existing SAJ Energy dashboard changed.
- Bumped cached card path to `/saj-h2-tou/v057/saj-tou-dynamic-card.js`; manifest `0.5.7`. GitHub CI validates syntax/offline tests; owner's browser must confirm appearance.


## 0.5.6 — 2026-11-02 (inverter controls visual alignment)

- Matched the owner's screenshot: placed **Refresh inverter state** in the right side of the unified Inverter controls header, rather than underneath the operating-mode buttons.
- Current device modes now appear inline beside Operating mode and Outside TOU windows; improved column alignment, button contrast, spacing, focus states and narrow-screen stacking.
- **No backend Modbus write behaviour changed**; existing one-confirmation actions and readback checks remain.
- Cache-busted the card at `/saj-h2-tou/v056/saj-tou-dynamic-card.js`.
- Owner's release policy: all incremental improvements remain small `0.x.y` versions; **v1.0.0 is reserved for the final stable, hardware-verified release**.


## 0.5.5 — 2026-11-02 (native page title and multi-inverter header picker)

- Changed the integration-generated Lovelace view title from **Time of Use** to **SAJ H2 Control**, including a safe one-time migration of the existing single-card storage dashboard.
- Added exact-match checks so user-customized dashboards and unrelated views are not overwritten, with offline migration tests.
- When multiple SAJ control devices are configured, display a clearly labeled inverter switcher immediately below the native HA toolbar; hide it for one inverter. Never attempt unsupported injection into Home Assistant's global toolbar.
- Frontend asset cache-busted to `/saj-h2-tou/v055/saj-tou-dynamic-card.js`. No changes to Modbus write behavior, authorization or separate SAJ Safe Monitor.


## 0.5.4 — 2026-11-02 (unified inverter control and visual polish)

- Followed owner's annotated dashboard screenshot: removed duplicate Battery time-of-use heading, hid single-device dropdown, and **joined Operating mode and Outside TOU windows into one full-width two-column panel** with a single outer border.
- Responsive control column stacking on small screens, clearer selected-mode button, improved table typography, restrained card styling, better schedule section and Save button prominence.
- No changes to backend Modbus writes, safety checks, confirmation popups or independent read-only SAJ Energy dashboard.
- Frontend cache-busted to `/saj-h2-tou/v054/saj-tou-dynamic-card.js`. GitHub CI checks code; visual layout requires owner browser review.


## 0.5.3 — 2026-11-02 (combined energy visualization + TOU controls)

- Recreated the owner's earlier **SAJ Energy → Live energy flow** five-column table inside the **independent SAJ TOU Control** dashboard: Solar, House, Battery, Grid and Forecast, using existing read-only Safe Monitor entities.
- Added compact live relative-power bars for Solar / House / Battery / Grid, a battery SOC bar, contextual charging/discharging/grid-flow text and current solar outlook. Missing readings show **—** rather than fabricated values. Grid direction remains provisionally labelled; forecast is only an estimate.
- Made read-only sensor updates refresh **only** the energy section, preserving focus/unsaved input in the TOU editor.
- Preserved actual inverter controls, one-confirmation Standby warning and backend write checks. **Neither the separate `saj_h2_safe` repository nor existing SAJ Energy dashboard were modified.**
- Replaced obsolete design-only README and developer handover with a full canonical current guide, preserved the old long development chronology in an archive, and corrected `docs/PROJECT_HANDOFF.md` entrypoint.
- Frontend cache-busted at `/saj-h2-tou/v053/saj-tou-dynamic-card.js`. This is a **visualization change**; no new Modbus writes or control semantics are introduced.
- The existing Standby write and broad schedule-write variants remain only partially field-validated despite offline tests; do not claim otherwise.

## 0.5.2 — 2026-11-02 (editable outside-TOU fallback)

- Added **Outside TOU windows** dropdown for Self-consumption (1) and Standby (0) using `0x365F`, with one mandatory Standby confirmation popup and no typed phrase.
- Full preflight and post-write Modbus verification of mode and both schedule blocks; no automatic retries.
- Updated mode and schedule code to recognise fallback 0 or 1. Added fake-Modbus fallback tests in CI.
- No completed on-device fallback write confirmation captured at release time.

## 0.5.1 — 2026-11-02 (power percentage and watts)

- Charging/discharging sliders show both **% and approximate W** simultaneously, based on paired elekeeper/Modbus samples (99 W per raw unit).

## 0.5.0 — 2026-11-02 (full schedule controls)

- Full 7+7 charging/discharging schedule editor, one Save workflow, explicit confirmation, full Modbus readback verification, weekday masks, and overnight split helper.
- Live schedule writes use individual register changes; incomplete transactions may leave partial settings. Fake-Modbus tests passed; some owner hardware combinations remain unverified.

## 0.2.4 — 2026-11-01 (second charging power pair)

- Owner confirmed the official eLEKeeper app **saved 6930 W** after a 7000 W charging setpoint request; Modbus Friday charge raw 70. Earlier app confirmed raw50→4950 W. Both support discharge-calibrated **99 W per raw unit** for readback.
- Decoder presents modeled charge watts `raw×99` across the slider with flags distinguishing direct confirmed raw 50/70 from modeled other raw values. No claim that predicted values are individually verified or actual delivered electrical power.
- Dynamic read-only card displays canonical saved charging watts and modeled preview watts. Tests cover exact raw70 snapshot and estimated raw51 case.
- Frontend cache-bust path `v024`; integration version 0.2.4. All controls still local preview-only and no HA Modbus writes.

## 0.2.3 — 2026-11-01 (confirmed Friday charging readback)

- New official eLEKeeper ↔ read-only Modbus paired test: **Friday charge 22:00–22:40, saved 4950 W** appeared as raw 0x3604 enable 1, packed time 5632–5672, weekday/power combined **4146 = 0x1032** (weekday mask 16 Friday; raw 50).
- Existing Wednesday discharge 22:00–22:40 remains **1074 = 0x0432** (weekday 4; raw 50).
- Mode 1 Time-of-use and TOU fallback 1 Self-consumption confirmed at same time; enabled charge **1/7**, discharge **1/7**.
- Read-only decoder labels **Friday (16)** and **Wednesday (4)** and conservatively recognizes combined mask 20, without guessing any remaining weekday bits.
- Charge saved-power display **4950 W is verified for raw 50 only**; other charging percentages remain unverified in the UI, not extrapolated.
- Dynamic card now shows Friday checkbox selected for the observed charge slot, updated source settings and distinguishes unverified values.
- Fixed source slot mapping of displayed saved values for nonconsecutive physical slots.
- Exact-device register snapshot and new tests recorded in `docs/SAJ_APP_TOU_OBSERVATIONS.md` and `tests/test_ha_tou_protocol.py`.
- Existing HA v0.2.2 still needs an in-place upgrade to v0.2.3. **No Modbus writes, no HA mode switch or real charging controls.**

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
