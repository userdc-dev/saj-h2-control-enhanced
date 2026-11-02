## v0.5.18 — Minimal dashboard, selectable sensor IDs and interactive solar forecasts (2026-11-02)

- Restructured Costs & savings to show three meaningful headline values first, with **Cost breakdown** and the long **Edit electricity tariffs** interface in separate collapsed panels. Existing time windows, user tariff selections, backend calculations, and ability to edit/switch rates remain unchanged. When no tariff has been saved, the editor opens for first-time setup.
- Rebuilt the Home Assistant Energy sensor reference as a concise collapsed section with four responsive groups (**Grid, Solar, Battery, Home**). Every actually discovered sensor exposes its **friendly name and exact entity ID** in a selectable, read-only field with a **Copy** button; never synthesise IDs. Includes signed grid power, separate import/export kWh/W and battery **energy charged**, **energy discharged**, signed power and SOC. Clipboard API falls back to selecting/copying the input for local HTTP/unsupported browsers.
- Added mouse-hover, touch and keyboard-accessible inspection to the **cumulative Actual vs projected solar chart** with a crosshair, forecast hour value, nearest actual Recorder point and actual sample time. Loads local-day solar history separately from the Historic Data range, refreshable on demand. Displays a partial-recording warning and **gaps in historical actual data as broken lines**, not continuous invented energy.
- Added hover/tap/focus inspection to seven-day and hourly forecast bars, showing precise available kWh and reported cloud percentage; collapsed the lengthy hourly list and saved PV model editor. Existing Historic Data signed-power graph and all prior hover behaviour remain in place.
- Added dependency-free **Node mock-DOM frontend smoke test** to GitHub Actions, checking actual dashboard methods and copy/hover interactions. No new Modbus write path, external repository, YAML configuration, or changes to existing sensor unique IDs.
- Full browser/mobile integration, meter polarity and forecast model accuracy still require owner testing.

## v0.5.17 — Energy power-measurement selection and true daily supply charge (2026-11-02)

- Added new distinct **Grid power • signed** (W, device class POWER, state class MEASUREMENT) for HA Energy **Standard** grid power measurement; retained and clarified the two existing import-only and export-only W sensors for HA Energy **Two sensors**, with a precise in-dashboard setup guide. Grid sign remains provisional until checked against the utility meter.
- Fixed the accounting error where the **daily supply charge was prorated by 10-second-class telemetry coverage** and thus showed only cents after a short monitoring period. The entire configured signed fixed supply charge (and selected taxes/levies) is posted **once per local calendar date**, even if no instantaneous power samples arrive.
- Preserves month-to-date daily charges, upgrades today's older v0.5.16 prorated amount to one full charge without counting it twice, prevents a mid-day tariff edit from charging supply twice, persists changes on setup, and keeps import/export energy charges limited to actual recorded intervals. Old flat-rate configurations also receive a full fixed daily supply charge.
- Provides separate **supply days counted** and **meter/tariff coverage hours** in Costs & savings; clarifies that days entirely offline before tariff tracking are not auto-billed, and the estimator is not a retailer invoice.
- Added offline regression tests for no-telemetry supply billing, legacy flat rates, month rollover, tariff edits, storage/restart persistence and v0.5.16 current-day migration. Existing TOU controls, forecast, dashboard, historical graph and Modbus write safety unchanged.

## v0.5.16 — Full signed time-of-use tariff schedules, special FiT and taxes (2026-11-02)

- Replaced the single flat-rate editor with editable multi-window import pricing: up to 12 user-defined rate categories (Peak, Off-peak, Solar sponge and additional), up to 24 windows per category, weekday selection, overnight wrapping, and a priced fallback for uncovered hours. Overlapping import windows are rejected.
- Added independent standard FiT windows, special high/battery FiT windows and separate fallback export price, all signed. Users must explicitly confirm that high FiT applies to all exports; battery-only/unverified eligibility uses conservative standard credit and shows potential high-FiT adjustment separately.
- Added GST-inclusive or GST-exclusive calculation, individual tax application flags for import/export/supply, user-defined signed additional tax/levy or rebate percentage, and negative or positive daily supply charge.
- Corrected billing model: interval-level, time-zone-aware pricing as recorded, split at minute/hour/night and local DST boundaries, 23/25-hour day supply-charge proration, unrounded stored running costs, separate coverage counters, per-band kWh/amount breakdown. Changes apply only to future observations; older monetary totals are never silently repriced.
- Added current active local import/export rate display on the Costs & savings tab and summary. Preserved original Home Assistant Energy aliases, existing estimated lifetime counters, TOU controls, live historical graph and solar forecast calibration.
- Added [Time-of-use tariff guide](docs/TIME_OF_USE_TARIFFS.md), safety notes, and offline regression tests for negative pricing, tax, weekend/overnight overlaps, interval splitting and DST.
- **Limit:** grid polarity and battery export origin remain unverified; estimates do not reproduce retailer settlement bills. No live AEMO feed, no automatic battery dispatch, no inverter writes introduced.

## v0.5.15 — Home Assistant Energy, signed electricity costs and measured forecast learning (2026-11-02)

- Added new read-only, clearly named HA Energy compatible solar production energy/power, battery charging/discharging energy, battery SOC/power and home energy/power aliases with correct device classes and long-term statistics state classes.
- Added **estimated** cumulative grid import/export kWh from conservatively integrated existing signed grid power; handles sign crossings, skips missing intervals, persists lifetime/day/month totals, and flags unverified polarity. Does not reinterpret ambiguous SAJ raw grid counters or rewrite the separate Safe Monitor.
- Added **Costs & savings** dashboard tab and summary with signed editable import/export tariffs and supply charges, today/month partial-period net cost, and carefully qualified combined self-supply value plus non-additive battery discharge potential. Future AEMO live pricing remains unimplemented.
- Added independent editable forecast self-calibration learned from at least 45 min of actual clear-sky power observations with SOC curtailment guard, per-hour bounded factors, and persisted history; resets calibration on changed model settings.
- Added [docs/ENERGY_AND_COSTS.md](docs/ENERGY_AND_COSTS.md) with manual Energy setup steps and warnings about duplicate meter inputs, assumed grid direction, incomplete coverage and price assumptions.
- Maintained all original TOU modes, fallback, 7+7 schedules, user confirmations, readback checks and no automatic Modbus writes. Offline CI is **not** browser/hardware verification.

## v0.5.14 — Inspect Historic Data with mouse, touch or keyboard (2026-11-02)

- Added crosshair and nearest-recorded-value detail panel to Historic Data. Hover or tap on the graph, or focus the graph and use left/right arrow keys to step through history.
- The cursor snaps to five-minute intervals for 6/12/24-hour views, ten minutes for 48-hour views, and thirty minutes for seven-day views; actual sensor readings retain their original timestamp and are never fabricated.
- Tooltip values show solar, house, signed battery and inferred signed grid (import minus export). Missing readings within half an interval show unavailable instead of stale or invented values.
- Kept the existing real-data graph, independent forecast, controls and Modbus safety measures untouched.

## v0.5.13 — Historic Data readability refresh (2026-11-02)

- Replaced the cramped Live energy history chart with a clearer **Historic Data** chart using a single kW scale, round-number ticks, subtle gridlines, better timeline labels and selectable 6h/12h/24h/48h/7d ranges.
- Removed cumulative solar Forecast (kWh) from this power-only chart; detailed forecasts remain available on the separate Solar forecast page.
- Kept signed battery power (positive discharge, negative charge) instead of losing direction through absolute values. Grid import is plotted above zero and export below zero using their existing separate read-only sensor entities; direction remains inferred until field-verified.
- Added decimation preserving within-bucket minimum/maximum points, and kept missing recorder intervals as gaps. No inverter write code or previously installed monitor files changed.

## v0.5.12 — Editable dashboard solar forecasts and Live energy history (2026-11-02)

- Added an in-dashboard Solar forecast page opened from the Live energy forecast column or Forecast details button, without affecting the TOU control screen.
- Added read-only Open-Meteo forecast computation from editable panel groups (9/15/6 panels, 440 W each; azimuth 29°/27°/299°, tilt 25°), efficiency (87%) and AC nameplate (10 kW) as *reviewable defaults*.
- Added editable settings service and HA forecast sensor. Settings save to the control integration configuration entry only, with backend validation; they do not write inverter registers or alter the previously installed Safe Monitor.
- Added day/hour forecasts, actual-versus-projected graph, and five selectable Home Assistant recorder histories in Live energy. Forecast uses its own energy axis; power series display magnitudes.
- Preserved existing control mode, TOU schedules, fallback, dashboard, original SAJ Energy and safety logic. The initial implementation requires real HA/browser checking; no inverter writes are used for forecast features.

# Changelog — SAJ H2 Control Enhanced

## 0.5.11 — 2026-11-02 (fully bundled monitor and simple one-command installer)

- Included **all seven source files** for the separate read-only Safe Monitor directly under `bundled_components/saj_h2_safe/` in this repository, with unchanged HA `saj_h2_safe` domain and monitoring logic. The Live energy section no longer requires visiting/downloading another repository.
- Reworked `scripts/install.sh` to fetch **only this repository**, install both controller and monitor from its single archive **by default**, and never overwrite an existing Safe Monitor. Backups of controller code remain outside `custom_components/`.
- Removed the obsolete `--with-safe-monitor` flag; `--control-only` is available for explicit controller-only installs.
- Promoted the exact one-block **curl → install → docker restart** commands for the original Kamrui HA setup in `README.md` and `docs/INSTALLATION.md`, with instructions to substitute a different HA config path on other hosts.
- First-run installation is via the HA UI for **SAJ H2 Safe Monitor** and **SAJ H2 Control Enhanced**, without `configuration.yaml` or Lovelace YAML/JS resource edits.
- Correctly documented that HACS normally installs the main controller domain only; full two-domain installation should use the bundled one-command script or manual file copy **from this repository**, not an external source.
- Added offline package and installer regressions proving the one-repository download, directory placement, Safe Monitor preservation, backups and no YAML modifications. No new Modbus write behavior.
- Version and frontend cache: **0.5.11** and `/saj-h2-tou/v0511/saj-tou-dynamic-card.js`. v1.0.0 remains reserved for final hardware-verified stability.




## 0.5.10 — 2026-11-02 (compact schedule controls, actual live status summary, zero-YAML packaging)

- The unified **Inverter controls** header now displays distinct live sensor states **Operating: [mode]** and **Outside TOU: [setting]**, not the static “Live mode · Outside TOU” label. Duplicate “Device: …” captions inside the two control columns were removed.
- The **Charging & discharging** section is more compact: **n/7** count and Add action share each card header, empty states are shorter, redundant “n configured on inverter” badges are gone, and the primary Save button sits opposite a compact Reload control.
- Removed the large always-visible technical warning; kept a short footnote on estimated W and manual recovery after an interrupted write. Critical multi-write risk disclosure remains in the save confirmation and errors.
- Added root **`hacs.json`** and complete **`docs/INSTALLATION.md`** for UI installation and upgrades from GitHub without `configuration.yaml`, custom Lovelace YAML, or manual JS resources. Integration auto-registers its frontend and independent dashboard when configured in HA.
- Added `scripts/install.sh` for Linux/Docker HA config directories. Safely backs up existing controller code outside `custom_components`; optional `--with-safe-monitor` installs the independent read-only Safe Monitor **only if missing**, never overwriting an existing one. Normal HA integration config flow is still required.
- Corrected the title for **new** SAJ Control config entries so they are no longer incorrectly called “read-only”. No migration of existing entries/entity IDs.
- Added packaging/UI regression tests (`tests/test_package_and_ui.py`), shell syntax validation, and replaced the obsolete planning-only “no Modbus write” CI grep. Existing simulated safety tests continue running.
- Version and cache path: **0.5.10** / `/saj-h2-tou/v0510/saj-tou-dynamic-card.js`. No new inverter write registers or authorization changes.
- Hardware certification remains limited to recorded tests; v1.0.0 is reserved for final release after comprehensive field verification.


## 0.5.9 — 2026-11-02 (visible live energy update frequency)

- Added a subtle **↻ Updates ~10 sec (default)** label beside the Live energy heading. Tooltip explains the Safe Monitor interval is configurable and forecasts refresh separately.
- Preserved the uncluttered header by not restoring the removed telemetry badge. No changes to polling, Modbus controls, refresh actions or data sources.
- Updated frontend cache-busting path to `/saj-h2-tou/v059/saj-tou-dynamic-card.js`.


## 0.5.8 — 2026-11-02 (Live energy header cleanup)

- Removed the redundant **Read-only telemetry** badge from the Live energy header, as marked in the owner's screenshot.
- No changes to sensor readouts, device controls or Modbus safety checks. Bumped frontend cache URL to `/saj-h2-tou/v058/saj-tou-dynamic-card.js`.


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
