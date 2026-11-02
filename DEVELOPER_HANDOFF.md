# Developer handover — SAJ H2 Control Enhanced

**Canonical current guide; updated 2026-11-02, Australia/Adelaide.** Read this before changing any code, dashboard, or Modbus control. **Current version at the time of this handover: 0.5.17.** The project was previously design-only, but now has a deployed Home Assistant control integration with working mode controls, schedule editing code, new fallback control, and read-only energy graphics/table within the TOU dashboard. **Not every writable feature has been proven on the owner's actual inverter.**

**Repository:** https://github.com/userdc-dev/saj-h2-control-enhanced  
**Older full development diary:** [docs/DEVELOPER_HANDOFF_HISTORY_THROUGH_V040.md](docs/DEVELOPER_HANDOFF_HISTORY_THROUGH_V040.md) (57 KB historical archive; early claims of “planning-only” are OBSOLETE)  
**Paired app evidence:** [docs/SAJ_APP_TOU_OBSERVATIONS.md](docs/SAJ_APP_TOU_OBSERVATIONS.md)  
**Bundled read-only monitor:** `bundled_components/saj_h2_safe` **inside this repository**. Preserve already installed `saj_h2_safe` and the owner's existing SAJ Energy dashboard; do not require another repository.  
**Current v0.5.17 CI evidence:** https://github.com/userdc-dev/saj-h2-control-enhanced/actions/runs/41379006231 — passed full Python/JS syntax, simulated Modbus safety, packaging, installer syntax and fake-archive install/update tests. This is **offline evidence, not live hardware certification**.

> The owner wants this file to be detailed enough that a human developer or future assistant with **only this repo and these notes** understands the purpose, chronology, code, register mapping, tests, successful live observations, unresolved issues, installation, safety constraints, and next actions. Do not delete or hollow out this handover. Keep it current whenever changing actual features.
>
> **Brand spelling preference:** call the SAJ mobile application **elekeeper** (lowercase) in all new messages and UI. Older archive entries may use the old capitalization.

## v0.5.17 — Home Assistant grid power selector and full daily supply charge (2026-11-02)

**Triggering user feedback:** The user supplied a screenshot of Home Assistant Energy → Electricity grid → **Type of power measurement** with radio choices **No power sensor / Standard / Inverted / Two sensors** and a required power statistic selector. They also showed the new Costs & savings UI calculating only around $0.02 with a configured daily supply charge of about $1.4944. The accounting wrongly prorated the supply fee by successful telemetry seconds; a utility daily fixed supply fee does NOT vanish when a monitor starts midday. The UI previously described supply as "prorated" and provided insufficient instructions for selecting grid power statistics.

**HA Energy sensor solution:** `sensor.py` adds stable unique ID `<entry_id>_energy_bridge_grid_signed_power`, friendly name **Grid power • signed (import + / export −)**, source `grid_power` from existing Safe Monitor, unit `W`, `SensorDeviceClass.POWER`, `SensorStateClass.MEASUREMENT`. In **Standard** choose this one signed power statistic. Under **Two sensors**, choose pre-existing `grid_import_power` and `grid_export_power` aliases (renamed friendly names **Power imported from grid • provisional** and **Power exported to grid • provisional**, same original unique IDs), each a nonnegative W measurement with correct HA metadata. **Inverted** only after independently verifying that the signed source uses opposite polarity. Do NOT alter or delete the original energy alias IDs. The integration remains read-only and reuses existing Safe Monitor data; signed grid register direction is provisional, so instruct users to compare against a known import/export condition on the utility meter before trusting costs or Energy. HA Recorder must include a numeric entity for at least one 5-minute statistics cycle before it appears under **Select a statistic**; check Energy/Statistics repair issues if absent. Explain that energy kWh counters and power W measurements are different and both can be configured. Details: [docs/ENERGY_AND_COSTS.md](docs/ENERGY_AND_COSTS.md).

**Supply accounting solution:** `tariffs.py` now supports `full_daily_supply(profile)` and `priced_slice(..., include_supply=False)` / `price_power_interval(..., include_supply=False)`; energy slices accrue energy cost **without** fractional fixed supply. `SajEnergyAccounting._ensure_daily_supply(when)` posts the **full fixed signed daily supply amount once per encountered local calendar date**, plus configured GST/levy/rebate, independently of grid-power readings. The month ledger stores `supply_charged_dates` keyed by local YYYY-MM-DD and corresponding amount/tax/revision; today's ledger also records its own fixed charge. Called at initialise, after saving a tariff, and on monitor updates/day rollover, including cases of missing grid readings. `supply_days_charged` is included in cost sensor details and UI, alongside separate grid energy coverage and tariff-priced interval coverage. If the same tariff is edited mid-day, the already-posted fee stays unchanged and cannot be charged again. If upgrading an older v0.5.16 day ledger with a prorated supply component but no date marker, it is reconciled to a **single full charge for the current day**, not added twice; earlier dates are left as previously recorded. Old flat-rate configurations use analogous `legacy_supply_charged_dates` and `legacy_supply_cost` rather than retaining the prior erroneous partial-day supply. Storage key and current kWh accumulated counters are unchanged. When tariff saved the cost ledger is persisted immediately.

**Billing limitations:** One full fee is posted on each tracked calendar day during operation; **days when HA was wholly offline and never observed are not automatically backfilled**. Even with full supply charges, energy costs may be incomplete during recorder outages and the resulting estimates are not legally or financially equivalent to a retailer bill. DST dates count one whole supply fee, not a fraction of a 23h or 25h day. Taxes on fixed supply use the user's selected signed percentage options. Never change or auto-write inverter operating mode/TOU registers as a side effect.

**Regression coverage:** `tests/test_energy_finance.py` also guards all three Home Assistant grid power aliases and their W/measurement metadata; `tests/test_tariff_accounting.py` tests full no-telemetry supply with $1.4944 example, zero double charge on repeated observations, midday edits using prior and new daily rates, month rollover, store/restart persistence, migration from old partial fee, and legacy flat full supply. Existing time-of-use/negative rate/DST/Modbus guard tests remain. Offline CI is not yet physical-browser verification; request post-upgrade screenshots showing the whole supply charge and the Power measurement statistic selector.

## v0.5.16 — Time-of-use tariffs, export eligibility, GST and accrual (2026-11-02)

**Owner request:** A basic flat electricity price is no longer sufficient. The Costs & savings page must support multi-period Peak (morning and evening), Off-peak, Solar sponge, user-defined extra import categories, editable weekday/weekend/overnight schedules, standard and special high battery-export FiT periods, signed rates, supply fees, GST and other levies/rebates. All features are self-contained in this repository; no separate dependency. Full UX and accounting reference: [docs/TIME_OF_USE_TARIFFS.md](docs/TIME_OF_USE_TARIFFS.md).

**Implementation and preservation contract:**
- **New pure pricing engine** `custom_components/saj_h2_control_enhanced/tariffs.py`: `validate_profile`, `choose_rates`, `tax_adjustment`, `priced_slice`, `price_power_interval`. Schema v1: `default_import_rate`, `import_bands` (id/name/rate/windows start/end/days indexed Monday=0), `export_standard_rate`, `export_standard_windows`, `export_fallback_rate`, `export_high_rate`, `export_high_windows`, `high_fit_eligibility` (`all_exports` or `battery_only_unverified`), `daily_supply`, `gst_percent`, `gst_mode` (`included`/`exclusive`), six `gst_on_`/`other_tax_on_` flags, `other_tax_percent`, `currency` and `configured`. Signed monetary rates ±100 in user-configured HA currency, GST 0–100%, extra levy/rebate −100 to 100%. At most 12 import bands, at most 24 windows each, with automatic reject for overlapping active weekday/minute intervals; fallback handles every uncovered import minute. An overnight window's selected weekdays mean the **starting** day.
- **FiT rules:** configurable standard and special high windows plus signed fallback; without explicit standard windows standard applies outside high periods. High only overrides standard when `high_fit_eligibility=all_exports` is explicitly user-confirmed. For battery-only special tariff, the source of exported electricity cannot be proven from currently available Safe Monitor watts; **use standard FiT**, show a separate possible difference from high FiT, and **do not add that potential amount to the accrued net cost**. Do not represent battery discharging coincident with exporting as proven battery export. A confirmed all-exports high FiT takes precedence over standard during overlaps.
- **State and save safety:** new HA service `saj_h2_control_enhanced.save_tariff_profile` receives a capped JSON payload, validates all fields, records the profile and `tariff_revision` ISO timestamp in the **existing controller config entry options**. Preserve old `save_cost_settings` for compatibility, without deleting a configured new profile. Before applying a new revision, flush the previously accrued ledger and clear the previous live-power sample so an interval cannot be priced half with the old plan and half with the new. This service never invokes Modbus write actions, does not alter inverter operating modes, TOU schedules, battery controls or the Safe Monitor.
- **Actual interval accrual:** extended `energy_finance.py` preserves existing `Store(hass, 1, "saj_h2_control_accounting_<entry_id>")` key, imported/exported cumulative kWh entity aliases, day/month snapshots and source coverage. It integrates only valid read-only grid power samples spaced 0–60s apart; splits an interval at UTC minute boundaries and converts each slice's midpoint into HA's **local timezone** for weekday/overnight/DST rate matching. Linear power changes and within-minute zero-crossings are split into separate import/export energy. Daily/month accumulated cost ledger tracks gross import cost, gross export FiT/fee, supply charge, extra tax adjustment, net expense, potential FiT adjustment, individual kWh+money category breakdown and eligible sample coverage **without retroactive repricing**. **Superseded in v0.5.17:** interval-based supply proration was removed; one full supply charge now applies per tracked local calendar date. Across restarts and tariff edits, previously accrued money stays unchanged. If an older flat-rate install has already recorded energy but no tariff ledger, the detailed-cost view initially shows unpriced energy; users must not assume historic intervals were valued at the new rates.
- **Frontend:** `frontend/saj-tou-dynamic-card.js` retains the previous energy/control, historic graph and forecast. Costs & savings now shows active tariff names/prices using backend HA local time, read-only today/month amount and coverage, full import and export breakdowns, editable multi-window category cards, weekdays and quick-select all/weekdays/weekend, signed rates, high FiT eligibility selector, separate GST inclusive/exclusive and component tax applicability, and a save action. User edits are held in memory without being reset on every 10-second sensor refresh; Save returns backend validation errors for overlapping windows. Do not hard-code the owner's own retailer rates as applicable to everyone; example values explicitly require user review.
- **Testing:** new `tests/test_tariffs.py` covers active morning/evening bands, weekends, overnight week wrap, conflicting schedules, signed import/export/fallback and rebate rates, high FiT eligibility, minute-boundary splitting, DST day-length supply charge and safe-readonly action presence. `tests/test_tariff_accounting.py` also simulates Home Assistant accounting end-to-end using fake HA coordinators and storage to verify that tariff changes do not reprice previous intervals, new rates begin only after a new power sample anchor, cumulative energy persists across reloads, and negative import/export fees have the correct customer-cost sign. Existing `tests/test_energy_finance.py` was updated for pure helpers; CI runs these alongside existing Modbus write policy and frontend syntax tests. These are OFFLINE tests, not proof of a Home Assistant browser end-to-end, a valid retailer bill, correct meter polarity, high-FiT dispatch eligibility or real inverter register writes.

**Known future work:** verify grid import/export direction against utility meter; test on physical HA browser/mobile, validate rate schedules against retailer contract; support explicit seasonal contract changes, demand tariffs, retailer APIs, and possibly confirmed dynamic AEMO-connected rates later. No automatic battery strategy or live pricing is shipped.

## v0.5.15 — HA Energy aliases, signed cost accounting, bounded PV learning (2026-11-02)

**Current implementation / entry point:** All new code lives in **this controller repository**, not in the pre-existing read-only monitor. Consult [docs/ENERGY_AND_COSTS.md](docs/ENERGY_AND_COSTS.md) for end-user setup and limitations. The old SAJ Energy dashboard, `saj_h2_safe` files, config-entry/entity IDs and all live-write Modbus safety functions remain unchanged. These features were added without on-device writes and without changing existing stored inverter schedules.

**Read-only data flow:**
1. `manifest.json` includes optional `after_dependencies: ["saj_h2_safe"]` so a configured monitor normally loads before the controller. `custom_components/saj_h2_control_enhanced/__init__.py` selects the existing `saj_h2_safe` config entry by recorded source entry ID or the same host and attaches listeners to its existing coordinator. No extra Modbus poller, no global YAML, no new external GitHub source. Controller still operates if the monitor is unavailable; after configuring monitor later, reload controller.
2. New `energy_finance.py` has pure `split_grid_energy()`, `estimate_cost()` and `estimate_benefit()`, plus `SajEnergyAccounting` using `homeassistant.helpers.storage.Store` for cumulative **estimated** grid import/export energy and day/month snapshots. It integrates 10-second-class read-only power samples only for gaps ≤60 sec; zero-crossing positive vs negative grid power energy is split mathematically, not cancelled. Gaps, restarts and earlier history are *not* backfilled. **Superseded in v0.5.17:** daily supply is charged in full once per tracked calendar date, irrespective of measured coverage. Grid polarity remains **inferred**: positive import, negative export; user must check meter.
3. New `SajEnergyBridgeSensor` in `sensor.py` provides **new unique IDs**, human-readable native source labels, `SensorDeviceClass.ENERGY` with `SensorStateClass.TOTAL_INCREASING` for energy kWh, `POWER` with `MEASUREMENT` for W, and `BATTERY` with `MEASUREMENT` for SOC %. It **does not rename or replace** existing safe monitor sensors. Native inverter lifetime counters `solar_total`, `battery_charge_total`, `battery_discharge_total`, `home_total` power these energy entities. Estimated grid totals come only from `SajEnergyAccounting`, not ambiguous raw `grid_sell_total` vs `grid_feed_in_total` registers.
4. `SajCostEstimateSensor` exposes daily estimated cost and attributes `today`, `month`, `pricing`, `saj_tou_role=cost_estimate`; UI reads that role in `saj-tou-dynamic-card.js`. New `save_cost_settings` service in `__init__.py` is **read-only to inverter** and writes signed flat rates + `configured` into only the controller's HA config-entry options. Rates: import rate positive expense, negative reward to import; export rate positive retailer payment, negative export fee; supply daily signed. **Superseded in v0.5.17:** estimated net cost includes one full fixed supply charge per tracked local calendar day, in addition to measured imports and exports. Current tariff source is user-editable STATIC; do **not** imply AEMO wholesale prices are imported, used as a retail bill, or influence automatic inverter modes.
5. Dashboard now has **Energy & controls / Costs & savings / Solar forecast** tabs and a compact Cost estimates section under Live energy. UI first prompts owner to review example tariffs, displays tracked today/month costs and coverage hours, combined self-supply & export value, and separately labelled **non-additive** battery discharge potential. Negative monetary numbers are allowed and not silently clamped. Savings are **illustrative** and cannot isolate grid-charged battery energy from solar self-consumption, nor compute an exact retailer bill.
6. `forecast.py` now includes its **own** persistent hourly calibration under `saj_h2_control_forecast_learning_<entry_id>`: clear-sky ≤25% cloud, at least 45 min real power sample coverage, expected ≥0.7 kWh, max SOC below 97% (avoid curtailment), slowly updated factor 0.85 previous + 0.15 observed/expected, clipped to 0.65–1.15. Uses monitor callbacks; no Modbus writes. Factors are retained across restarts and discarded when panel groups/efficiency/AC reference change; no automatic backfill of historical data from before feature install. Existing Safe Monitor solar learning is not modified.
7. `tests/test_energy_finance.py` covers signed prices, positive and negative grid watts, zero crossings, incomplete intervals, coverage prorating and guarded savings. `tests/test_forecast_dashboard.py` and `tests/test_package_and_ui.py` cover structural availability and original write controls. CI tests are *offline* (Python AST/syntax + Node JS parsing + fake-Modbus tests) and do **not** certify browser integration, meter polarity or physical inverter state. Ask owner for screenshots / HA log errors before claiming a live successful deployment.

**Known limitations / follow-ups:** Browser usability and test on the installed Home Assistant 2026 version are still outstanding. The initial integration needs a configured safe monitor; on some setups reload controller after adding one. Reverify grid signed direction against a real utility import/export meter. Extend accounting to time-dependent tariffs, taxes, export penalties, demand charges and AEMO-connected prices only after precise data sources are identified; do not present static model as live AEMO rate or exact billing. Do not merge estimated lifetime totals with true utility counters and never auto-alter inverter TOU schedules from pricing. Keep the last approved Historic Data chart exactly as before (instantaneous kW, crosshair, recorded timestamps).

## v0.5.14 — Confirmed Historic Data semantics and owner UI review (2026-11-02)

**Owner-visible browser evidence:** The owner installed the updated controller, supplied screenshots of the Historic Data graph, and confirmed that the improved display and hover inspection are substantially easier to read. The screenshot at **2 November 2026, approximately 10:30 AM Adelaide time** showed cursor readbacks of **solar production 10.48 kW**, **house usage 2.80 kW**, and **battery −7.67 kW**, with grid reporting **“no nearby reading.”** These are *observed UI values*, not an independent raw Modbus or calibrated-meter verification. Do not claim the grid was zero or that it had a verified direction. The owner said the graph was satisfactory and asked specifically to document the semantics rather than alter the implementation.

### Important: instantaneous power versus cumulative energy

- **Historic Data solar (yellow)** is `sensor.saj_h2_safe_monitor_total_solar_power`, based on the read-only Safe Monitor's instantaneous `total_pv_power` (combined PV strings, **W**, displayed as **kW**). It is **not** daily cumulative solar energy (kWh). A rising morning line can represent increasing irradiance and PV output, not accumulation. The caption **“Solar production”** is power, not a lifetime/daily energy counter.
- **House usage (blue)** is instantaneous `sensor.saj_h2_safe_monitor_home_consumption` (**W**, displayed as **kW**).
- **Battery ± (green)** is instantaneous signed battery power. Existing convention: **positive = discharging**, **negative = charging**. E.g. −7.67 kW indicates battery charging at roughly 7.67 kW at that sampled moment.
- **Grid ± (purple)** uses separate read-only `grid_import` and `grid_export` entities. Historic Data draws import positive and export negative, using a *provisional/inferred* polarity mapping; do not label this as field-verified. The hover summary combines both only when each has a nearby recorded reading; otherwise show unavailable, not an assumed zero.
- Forecast **kWh** is deliberately **excluded from Historic Data**, to avoid mixing cumulative/projected energy with measured instantaneous power. Forecast, actual-versus-projected energy, daily energy and hourly energy estimates belong on the independent **Solar forecast** dashboard page. Do not integrate forecast series into the Historic Data power axis.
- Units matter: **kW = rate of power at a specific moment**; **kWh = energy delivered over an interval**. An approximate instantaneous balance in a screenshot does not independently validate sensor calibration or direction.

### History UI contract — preserve unless explicitly requested

The live `custom_components/saj_h2_control_enhanced/frontend/saj-tou-dynamic-card.js` graph uses Home Assistant's recorded `history/period` states and a **single kW axis** for the four power measurements, with zero baseline and negative battery/grid values below it. It has 6 h, 12 h, 24 h, 48 h and 7 d ranges; four separately selectable lines; legible tick intervals, responsive layout and minimized lines between missing intervals. Historic Data **does not fabricate samples**, does not average cumulative energy into an instantaneous reading, and makes **no Modbus writes**.

Mouse hover / touch tap / focused keyboard left/right arrows select a time and show a vertical guide, colored markers and individual real recorder values with their **original sample timestamps**. Cursor time snaps at **5-minute** intervals for 6/12/24-hour views, **10-minute** intervals for 48 hours and **30-minute** intervals for 7 days. Inspection chooses the closest recorded sample only if it lies within **half the corresponding interval**, otherwise displays *no nearby reading*. This time-step snapping applies **only to cursor inspection**, not to Recorder sampling frequency or the plotted raw state history. **Do not describe the tooltip as an exact reading at the snapped minute**: it is the nearest eligible actual sample, identified by its recorded timestamp.

**Preservation:** Owner-approved layout, interactive hover/touch/keyboard behaviour, one-axis kW semantics, separate forecast page, TOU operating-mode controls, editable 7+7 schedules, fallback/Standby confirmation, and all established safety/verification gates must remain intact. No live Modbus write test or new hardware verification occurred during this documentation change.

## 0. Single-repository packaging and installation (2026-11-02)

**Owner requirement:** A complete installation must obtain all needed source exclusively from `userdc-dev/saj-h2-control-enhanced`, with a short copy/paste Docker command. The existing `scripts/install.sh` already downloads one repository archive and installs both `saj_h2_control_enhanced` and bundled `saj_h2_safe` (monitor only if missing) by default. The old text describing `--with-safe-monitor` and fetching a second repo was inaccurate and has been superseded.

**Public-facing generic example (replace the configuration path and container name before running):**
```bash
curl -fL https://raw.githubusercontent.com/userdc-dev/saj-h2-control-enhanced/main/scripts/install.sh -o /tmp/install-saj-h2.sh &&
bash /tmp/install-saj-h2.sh /home/USER/compose-files/homeassistant/config &&
docker restart homeassistant
```

`/home/USER/compose-files/homeassistant/config` is a placeholder, not an automatic discovery mechanism; other Docker layouts may have a different path entirely. For the recorded owner's host, replace it with `/home/kamrui/compose-files/homeassistant/config` (and use `homeassistant` as its known container name). This Docker command is not portable to HA OS or arbitrary container names. The monitor retains its own domain/config entry for compatibility. **HACS-only controller installation does not presently deploy `bundled_components/saj_h2_safe`**; never claim it does. Do not auto-write Modbus, change existing monitor entity IDs or overwrite an already installed monitor. Treat this packaging/docs fix as non-runtime: no inverter-control code was changed and no new hardware verification was performed. The single authoritative user guide is [docs/INSTALLATION.md](docs/INSTALLATION.md).

## v0.5.12 — In-dashboard forecast and recorded history (2026-11-02)

The control integration now includes **its own read-only weather forecast coordinator** in `custom_components/saj_h2_control_enhanced/forecast.py`. Do **not** confuse it with, delete, rename, or overwrite the pre-existing `saj_h2_safe` SolarCast monitor. Forecast settings are stored in the existing control entry's `options`: `forecast_groups`, `forecast_efficiency`, `forecast_ac_limit_kw`, and `forecast_configured`. The read-only `save_forecast_settings` HA service validates 1–8 panel groups and only updates this configuration data and requests new weather; **never any Modbus writes**. The separate sensor entity with `saj_tou_role=editable_forecast` publishes its daily modeled kWh and attributes (`daily`, `hourly_today`, `settings`).

The dashboard JavaScript now offers **Energy & controls / Solar forecast** page navigation inside the existing dynamic card (no migration of customized Lovelace layouts). The Live energy forecast header and values open the forecast page. It shows weather-driven today/remaining/tomorrow/seven-day and hourly forecast, actual-vs-projected chart sourced from HA recorder history, and an editable 9/15/6 × 440 W group model (azimuth 29°/27°/299°, tilt 25°, efficiency 87%, AC reference 10 kW) as defaults. Show a visible owner-customization warning until settings have been saved. The AC limit is a reference, **not a hard cap on PV-side energy**, because DC battery charging may coexist with AC load. The old Safe Monitor's adaptive learning is not silently changed; this new editable weather model currently does not inherit its proprietary self-learning adjustments.

The Live energy section has a history graph using Home Assistant's `history/period` API with six-hour through seven-day windows, selectable Solar, House, Battery, Grid import/export magnitude and Forecast history; power plotted using the left axis (kW) and forecast energy using the right axis (kWh). Do not fabricate missing data; each time series comes from recorded HA states. When a customized forecast is enabled, its numeric kWh sensor is used for forecast history, so its historical chart may initially be empty. Real weather responses, HA recorder permissions, mobile UX and full interactive operation **still require testing on a live HA instance**. The CI contains offline syntax and structural tests, not real inverter/hardware or end-to-end browser tests.

**Safety preservation:** No changes were made to legacy `supervised_write.py`, `supervised_fallback.py`, `schedule_transaction.py`, `tou_protocol.py` or existing saved TOU control entries. The new settings action is read-only relative to inverter hardware. The installer preserves old Safe Monitor files on upgrade.

## 1. Goal, scope, and user requirements

There is already a stable, independent **read-only** Home Assistant integration, domain `saj_h2_safe`, and an owner's dashboard **SAJ Energy** showing solar, house consumption, battery state and energy forecast. This repo provides both the **separate-domain** writable control layer and a bundled copy of the read-only monitor for installations missing it. It must NEVER overwrite, merge, rename or break the read-only monitor, and it must not modify the existing SAJ Energy dashboard without a specific request.

The end goal is a polished dark/grey Home Assistant experience providing:

- Clear **operating-mode** controls, Self-consumption (raw mode 0) / Time-of-use (raw mode 1), with verified device readback.
- Editable **Outside TOU windows** behaviour, Self-consumption (raw fallback 1) / Standby (raw fallback 0). When Standby is selected, **one clear confirmation popup** must warn that battery use/grid behaviour may change. Confirm once; **NO extra prompt to type confirmation phrases**.
- Up to **seven charging** and **seven discharging** scheduled periods; editable start/end 24-hour times, weekdays, power setpoints, enabled slots; add/remove; saved vs unsaved clearly separated; automatic readback and conflict detection; one intuitive **Save** button. Slider must show **raw % AND estimated W simultaneously**.
- A helper for **midnight-crossing** requests: elekeeper cannot store one 23:00–01:00 slot; owner explicitly explained it requires separate 23:00–23:59 on the original weekday and 00:00–01:00 on the following weekday; UI supports **Split overnight into two schedules** when another free slot exists.
- Read-only contextual graphics and compact tables based on the earlier SAJ Energy **Live energy flow** card; never invent sensor data. Preserve the existing monitor and dashboard; integrate the graphics in this project's UI rather than editing the owner's safe-monitor code.
- Later, short-term forced charge/discharge with custom minutes, countdown, cancel, watchdog, stop and verified recovery; price/solar automation, OCPP EV charging and HVAC orchestration. **These last features are NOT shipped** and should not be described as working.

User prefers concrete coding and short copy-paste setup commands over long reassurance, standalone full replacement config where appropriate, no repeated questions about already-known hardware, and rapid iteration with careful actual testing.

## 2. Exact known hardware, software and topology

| Property | Recorded evidence |
|---|---|
| Inverter | **SAJ H2-10K-S3-A**, 10 kW class |
| Control board | **v2.018**, confirmed by owner's elekeeper screenshot |
| Display board | **v5.042** |
| Battery | SAJ B2 nominal **40.96 kWh** reported by owner; older SAJ app capacity displays also refer to 40.00 kWh. Never use this difference to infer writable limits |
| Solar | Approximately **13.3 kW** PV (30 × 440 W bifacial panels) |
| HA environment | Docker container **homeassistant** on a Debian-based Kamrui N95 mini PC; HA config is a host-mounted bind directory |
| Inverter protocol | **Modbus TCP**, TCP port **502**, slave / device ID **1** |
| Connection | Config flow can reuse the independent `saj_h2_safe` monitor config entry or use manually supplied IP/port |
| Dashboard | Independent **SAJ TOU Control** sidebar; path `/saj-tou-control/tou`, one custom `saj-tou-dynamic-card` |
| Integration domain | `saj_h2_control_enhanced` |
| Frontend URL (v0.5.10) | `/saj-h2-tou/v0510/saj-tou-dynamic-card.js` |
| Normal readback interval | Default **120 seconds** (configurable 60–3600 seconds) |
| Python dependency | `pymodbus>=3.6.9,<4` |
| Separate monitor | `saj_h2_safe` — never overwrite or remove |
| Independent old dashboard | `SAJ Energy` — never overwrite or remove |

Do **not** place the owner's private IP address, street address, SSH credentials, device tokens or private screenshots in the public repository. Use live configuration / user's current SSH session for host-specific commands.

## 3. Implementation status: what is genuinely verified

**Differentiate these four levels:** (a) source implemented, (b) unit tests passed with fake Modbus, (c) a command/readback succeeded on the actual inverter, (d) elekeeper later displayed the same saved setting. Only explicitly recorded owner evidence supports (c)/(d).

| Feature | Source/CI | Owner hardware evidence |
|---|---|---|
| Full TOU register readback; 7+7 slots, mode, fallback | Implemented / tests | **Confirmed** against multiple elekeeper screenshots |
| Switch mode 0→1 | Implemented / tests | **Confirmed**: backend returned `VERIFIED_BY_MODBUS` and elekeeper showed TOU |
| Switch mode 1→0 | Implemented / tests | **Confirmed**: backend returned `VERIFIED_BY_MODBUS` and elekeeper showed Self-consumption |
| Dashboard live mode buttons | Implemented / tests | **Confirmed** at least one live TOU switch through card |
| Schedule editor (time/day/power/add/remove) | Implemented / tests | Multiple screenshots show editable UI and saved readbacks. **Do not claim every write combination hardware-tested** |
| Full schedule save `apply_schedules` | Implemented / fake transport tests | Screenshot showed `Applying & verifying…`; later device had changed active schedule values (Sunday charge and no discharge), but **complete successful service response / all edits' provenance not captured** |
| Save while TOU active (temporarily mode1→0→1) | Implemented / fake tests | **Not individually confirmed as complete hardware transaction** |
| Outside-window Standby/Self-consumption write `0x365F` | Implemented in **v0.5.2** / fake tests | **Readback semantics observed**. New live write **not yet independently confirmed** by owner |
| Standby warning popup | Implemented in card / backend tests | **Not yet verified by owner's screenshot after installation** |
| Mode/fallback interaction when Standby selected | Code supports raw fallback 0/1 | End-to-end hardware testing outstanding |
| Mon–Fri day mask | Decoder/tests | Confirmed by paired app/readback, including Tue+Thu |
| Sat+Sun combined mask `96` | Decoder/tests | Combined app/readback confirmed; standalone Sat=32 and Sun=64 inferred |
| Raw charge/discharge power mapping | Display/tests | Specific elekeeper pairs support **99 W per raw percent**, not actual delivered electrical power |
| Crossing midnight in one device slot | Deliberately unsupported | Owner explicitly confirmed elekeeper uses **two separate slots** |
| Timed forced charge/discharge, watchdog, EV/HVAC automation | **Not implemented** | No hardware test |

**Historical first schedule known to be correct:** Friday charge 22:00–22:40 at raw70 = 6,930 W; Wednesday discharge 22:00–22:40 at raw50 = 4,950 W; charge/discharge enable masks = 1, fallback = 1. **DO NOT ASSUME THIS IS STILL SAVED:** the user's subsequent screenshot showed **Sunday charge 08:00–08:30 (raw low power), no discharge periods**. Always read the actual device before planning a write.

## 4. Authoritative Modbus TOU layout and encodings

**Read full device snapshot:** charge registers `0x3604` count **23**, discharge registers `0x361B` count **21**, mode `0x3647` count 1, outside fallback `0x365F` count 1. Compare **two complete readbacks** for consistency.

| Register(s) | Meaning | Encoding |
|---|---|---|
| `0x3604` | Charging slot enable mask | bit 0→slot1 through bit6→slot7; 0–127 |
| `0x3605` | Discharging slot enable mask | same mask |
| `0x3606–0x361A` | Charging slots 1–7 | 3 words per slot |
| `0x361B–0x362F` | Discharging slots 1–7 | 3 words per slot |
| `0x3647` | Inverter operating mode | 0 Self-consumption; 1 TOU; **2 Backup / 3 Off-grid-Passive blocked** |
| `0x365F` | Outside TOU fallback | **0 Standby**, **1 Self-consumption** |

Each slot comprises: first word **start clock**; second word **end clock**; third word **(weekday mask << 8) | raw percent**. Hour is high byte and minute low byte; `22:00` = `0x1600` = 5632; `22:40` = `0x1628` = 5672; `21:30` = `0x151E` = 5406. Valid schedule times are 00:00–23:59. Do not put 24:00 in a Modbus word.

Weekday mask: Monday=1, Tuesday=2, Wednesday=4, Thursday=8, Friday=16 **paired confirmed**; Saturday=32, Sunday=64 **individually inferred**, combined Saturday+Sunday=96 **observed**. Don't claim individual weekend mapping was experimentally verified until it actually is.

**Example raw schedule words:** Friday charge at raw70 = `0x1046`; Wednesday discharge at raw50 = `0x0432`. Expected watts for UI labels = **raw percent × 99 W** (e.g. 50→4,950 W; 70→6,930 W; 98→9,702 W; 100→9,900 W). Specific samples were paired to elekeeper. Other values are **display estimates**, **not** measured AC power or proof of delivered rate.

Disabled slots can retain stale time/day/power words. Always trust the **enable mask**, not all nonzero stored words. The read-only decoder's `Config.summary("charge"/"discharge")` returns **enabled** slots only.

Elekeeper does not accept an overnight period such as 23:00→01:00 as a single slot; create **23:00→23:59 original weekday** plus **00:00→01:00 following weekday**. The card has a split helper. Whether there is a true gap at the 23:59–00:00 boundary depends on device interval semantics and has not been electrically measured; don't promise seamless operation.

## 5. Source tree: what to edit for which change

### Installed HA integration: `custom_components/saj_h2_control_enhanced/`

| File | Responsibilities / danger |
|---|---|
| `manifest.json` | Domain, version, Python dependency |
| `const.py` | Port, ID, scan period |
| `config_flow.py` | Owner-confirmed HA setup; reuse safe monitor settings; no LAN sweep |
| `__init__.py` | HA read coordinator, async services, shared `pilot_lock`, lifecycle; changes here affect live services |
| `tou_protocol.py` | Data decoder: full 7+7 layout, modes/fallback, power words, slot state/change detection |
| `sensor.py` | Read-only *state reporting* and attributes; setting actions do not mean sensor values become speculative |
| `frontend_setup.py` | JS static URL and independent dashboard creation; **increment versioned URL when JS changes** |
| `frontend/saj-tou-dynamic-card.js` | Card UI, device auto-binding by `saj_tou_role` / `saj_tou_entry_id`, state vs local drafts, mode buttons, outside-window dropdown, Standby warning, full schedule Save, time picker, overnight split, %/W sliders |
| `supervised_write.py` | Single FC06 mode write at `0x3647` with pre/post whole device readback, only raw modes 0/1 |
| `supervised_fallback.py` | Single FC06 fallback write at `0x365F` with explicit Standby confirmation and unchanged mode/schedule verification |
| `schedule_transaction.py` | Complete 7+7 schedule plan, changed-word writes, masks committed last, optional temporary mode 1→0→1, full readback after every write |
| `schedule_preview.py` | Legacy read-only single-slot plan |
| `supervised_schedule_write.py` | Legacy hard-coded Friday charging pilot, **not current general Save flow** |
| `services.yaml` | Developer Tools service definitions, legacy descriptions may lag current functionality |
| `strings.json` | Config flow localization |

### Other directories

- `control_core/` holds **earlier disabled design prototypes**; e.g. its `supervised_mode_engine.py` has a no-write gate. **Do not mistake this for the installed live runtime**.
- `tests/` has fake-Modbus unit tests and protocol fixtures.
- `docs/SAJ_APP_TOU_OBSERVATIONS.md` contains the detailed step-by-step paired elekeeper evidence and timing.
- `docs/DEVELOPER_HANDOFF_HISTORY_THROUGH_V040.md` is the historical development diary. Earlier entries saying **NO WRITE IMPLEMENTED** were accurate *then* and are **no longer current**.
- `docs/FUTURE_SMART_LOADS.md` covers proposed OCPP/HVAC work.
- `.github/workflows/safety-tests.yml` runs Python compile, JS syntax, simulated tests. Its legacy “Reject Modbus write implementations” step is a simplistic regex check and **does not certify that this repo has no write paths**.

## 6. Data flow and backend service contract

HA startup registers the dynamic static card and initializes its independent dashboard. The coordinator polls the inverter via Modbus and publishes seven sensor roles: `operating_mode`, `outside_schedule`, `charge_count`, `discharge_count`, `charge_schedules`, `discharge_schedules`, `sync_status`. Each has `saj_tou_role` / `saj_tou_entry_id` attributes. The JS card selects the correct device by these attributes, not hard-coded entity IDs.

**Important:** a user editing a draft changes **only frontend local state**. The real inverter doesn't change until the backend confirms a write. Browser hard refresh discards unsaved edits. Once the write is verified, the frontend requests fresh coordinator state and displays saved new values.

### HA services, domain `saj_h2_control_enhanced`

| Action | Effect / response |
|---|---|
| `preview_mode_change` | Fresh readback only, `DRY_RUN_ONLY` |
| `supervised_tou_pilot` | Authorized `0→1` single mode write, `VERIFIED_BY_MODBUS` |
| `supervised_self_consumption_pilot` | Authorized `1→0` single mode write, `VERIFIED_BY_MODBUS` |
| `supervised_outside_tou_fallback` | New v0.5.2 `0x365F` one-word write, `FALLBACK_VERIFIED_BY_MODBUS`; required arguments `target_fallback`, `expected_fallback`, `expected_mode`, model, firmware, and `standby_confirmation` when target 0 |
| `plan_schedules` | Full 7+7 expected-vs-current validation **without write**, `SCHEDULE_PLAN_ONLY` |
| `apply_schedules` | Full 7+7 live write and verification, `SCHEDULE_VERIFIED_BY_MODBUS` |
| `preview_schedule_change` | Legacy single-slot preview, **not** Save |
| `supervised_friday_charge_time_pilot` | Earlier hard-coded Friday pilot; keep for backwards compatibility until audited |

The full editor passes **both** expected and proposed charge/discharge arrays to the backend. An original enabled slot is shaped like:

~~~json
{"slot":1,"start":"22:00","end":"22:40","day_mask":16,"percent":70}
~~~

A proposed enabled slot is shaped like:

~~~json
{"slot":1,"start":"21:30","end":"22:00","days":["Fri"],"percent":70}
~~~

The frontend passes the backend's fixed confirmation field **after the one user-visible popup**, not an additional phrase-entry window. Such frontend strings are **not real authorization/security controls**; HA access permissions and network boundaries are crucial.

## 7. Safety contract and transaction order

1. **Explicit user action only**. Never write on startup, polling, dashboard render or background forecast updates.
2. Confirm exact device profile: H2-10K-S3-A control firmware v2.018. Code uses asserted profile strings; it is **not an independent hardware identity attestation**.
3. Disallow operating modes **2 and 3**, unsupported fallback codes, invalid active-slot content or masks outside 0–127.
4. Use read-only double snapshots before any write. Compare complete charge/discharge blocks, mode, fallback; abort if changed.
5. Check the owner's **entire current enabled schedule baseline** against the draft. External elekeeper/VPP edits can occur and invalidate the draft.
6. One HA-process `pilot_lock` serializes write paths; it doesn't prevent commands from outside HA.
7. **Function-06 one-register writes**, **no automatic retries**, **no blind rollback**. A timed-out write might have succeeded despite missing acknowledgment.
8. Schedule writes: write only changing words, put new slot words before enabling its mask; update enable masks **last**; read full state after **every** write. Existing active start/end word ordering is chosen to avoid transient backwards intervals where possible.
9. If schedule Save begins in Time-of-Use mode 1, code temporarily switches to mode 0 for the multi-register update and restores mode 1 **only after all words verify**. A failure can leave device in mode 0 and schedule partially changed. **This full transaction has simulated tests but is not fully field-validated**.
10. Fallback write to `0x365F` is a separate one-word action. Selecting Standby must show a popup explaining likely battery/grid impact. Verify **only fallback** changed; mode, both schedule blocks are unchanged.
11. If any command might have been sent and the readback is ambiguous: **STOP, do not click Save again**. Inspect both schedule groups, operating mode and fallback in live Modbus/elekeeper first.

**Not atomic:** HA + Modbus cannot offer transactional rollback of multiple 16-bit registers. The hardware can be left partially modified by network loss, HA reboot, inverter reboot or external control. Avoid describing an error response as proof nothing changed.

**Competing control:** The owner's elekeeper screenshots have shown an **“Under third-party control”** banner following past VPP connection. The exact status/revocation is unresolved. A cloud or VPP controller may overwrite writes. If mode/settings change unexpectedly, investigate instead of trying to win a repeated write race.

**Do not touch** SOC reserve, BMS safety, inverter backup/off-grid mode, off-grid load backup toggle, AC coupling, voltage/export parameters or any other unsafe setting as a side effect.

## 8. Live UI behaviour to preserve

- **Operating mode** buttons reflect **readback state**, not just last button pressed. Disabled when current/unsupported/stale; with confirmation popup; elekeeper overview may lag direct Modbus for minutes. Standby outside-TOU may coexist with TOU; warn on mode change.
- **Outside TOU windows** selector shows `Self-consumption` and `Standby`; selection resets visually until confirmed from Modbus; Standby asks **one confirmation popup**. No phrase prompt. This is distinct from setting the operating mode itself.
- **Charging/discharging** 0–7 rows each; native HTML `type=time` inputs; Mon–Sun checkboxes; power slider **1–100% with both % and approximate W**; saved values always labeled separately.
- **Save schedule changes to inverter** is the only necessary user workflow: internally plan, show **one confirmation**, write and verify; no mandatory manual dry-run button.
- **Split overnight into two schedules** when row start > end and another slot exists. Follow-weekday rollover includes Sunday→Monday. A single overnight slot must remain rejected.
- **Discard edits/reload inverter** intentionally discards local edits (with warning) and reloads saved settings. A browser refresh also loses local drafts.

**Current source sometimes contains older strings (e.g. service names with “pilot” or config-flow title “read-only”).** Modernize only with entity-ID-safe migration; do not delete/recreate working integrations.

## 9. Tests, release and installation

At handover, v0.5.2 passed offline GitHub workflow **41319913554**. CI includes:

- Python compile and Node `--check` on dynamic card.
- Unit tests covering `tou_protocol`, reading, telemetry, reconciliation, old mode model.
- `tests/test_schedule_transaction.py`: add/change/remove; masks last; no-op; invalid overlap/time/power, failure no retry; mode1→0→1 fake transport.
- `tests/test_supervised_fallback.py`: one register only, standby authorization, reverse to Self-consumption, competing mode, stale preflight, missing acknowledgment.
- **No direct physical inverter/network I/O in CI.** Browser JS checks syntax, not DOM behaviour, mobile layout, or real HA WebSocket responses.

Example local commands from repo root:

~~~bash
python -m compileall -q control_core custom_components tests
node --check custom_components/saj_h2_control_enhanced/frontend/saj-tou-dynamic-card.js
python -m unittest discover -s tests -p 'test_schedule_transaction.py'
python -m unittest discover -s tests -p 'test_supervised_fallback.py'
~~~

### Update the installed HA integration

Owner uses SSH into the host and Docker. **Do not delete the integration or dashboard entities**.

~~~bash
# Set the actual HA configuration directory on the owner's host.
HA_CONFIG="/path/to/homeassistant/config"
cp -a "$HA_CONFIG/custom_components/saj_h2_control_enhanced" "$HA_CONFIG/custom_components/saj_h2_control_enhanced.backup"
tmp="$(mktemp -d)"
curl -fL https://github.com/userdc-dev/saj-h2-control-enhanced/archive/refs/heads/main.tar.gz -o "$tmp/repo.tar.gz"
tar -xzf "$tmp/repo.tar.gz" -C "$tmp"
cp -a "$tmp/saj-h2-control-enhanced-main/custom_components/saj_h2_control_enhanced/." "$HA_CONFIG/custom_components/saj_h2_control_enhanced/"
docker restart homeassistant
~~~

**Caution:** `main` moves; for reproducibility use a known tag/commit SHA in production. If JS changes, increment the versioned URL in `frontend_setup.py` (v052→v053 etc), restart HA and refresh browser. If the old card still appears, inspect browser cache and registered HA JS resource.

Restoring the backed-up **code** does **not** revert already-saved inverter settings. Always check live readback separately.

## 10. Troubleshooting — first safe checks

| Symptom | Likely cause / action |
|---|---|
| Old UI after update | Cached JS asset; verify static URL version, HA restart, hard browser reload |
| Grey mode button | Stale device readback, local unsaved draft, action busy or unsupported mode; check displayed blocker; refresh inverter state |
| Save disabled | No changed draft, unsupported operating mode, or control busy |
| Unsaved edits revert on page refresh | Local draft wasn't saved; source of truth remains device |
| Schedule saved in elekeeper but old dashboard values | Coordinator polling interval; force readback and check full masks/slots; app can lag |
| “Validation blocked: stale draft” | An external controller or elekeeper changed current settings; discard/reload, do not override without seeing differences |
| `SCHEDULE_PLAN_ONLY` | A read-only preview, **not** proof a write was sent |
| “Applying & verifying…” never finishes | Check HA logs, WebSocket response and full Modbus status; never blindly repeat potentially sent command |
| Timeout/missing ACK | Command might have succeeded; check device first. No automatic retry |
| A schedule edit leaves mode Self-consumption | Multi-register transaction may have paused TOU and failed before safe restoration |
| Weekend checkbox saves wrong day | Individual Sat/Sun mask still needs independent paired app testing; source code currently accepts inferred bit32/64 |
| Standby dropdown visually reverts | Deliberately uses authoritative readback; inspect HA action result and `0x365F` |
| Unexpected battery imports after Standby | Standby may alter battery participation outside slots; owner must be warned before change |
| Shown wattage differs from actual delivered watts | Stored raw setting ×99 W is a calibration **label**, not measured output |
| elekeeper overview lags mode | App overview delay observed approximately five minutes; detailed operating mode view and direct Modbus update sooner |

## 11. Known gaps and highest-priority next work

**P0 — complete proof and safety:**

- Confirm owner has actually installed v0.5.2; **GitHub commits do not install updates**.
- Controlled live testing of `supervised_outside_tou_fallback` with Standby popup; verify final Modbus status, unchanged both schedule groups, and matching elekeeper display. Reverse test Standby→Self-consumption; do not retry ambiguous commands.
- Capture full **successful schedule Save response** plus final elekeeper schedule snapshot; code is functional/offline-tested but not independently field-certified for all 7+7 combinations.
- Test Sat-only and Sun-only bit behavior against the mobile app and no unintended weekday.
- Review standby interactions with mode-switch checks, schedule writes, concurrent external VPP commands, HA restarts, loss of connection, DST and midnight.
- Add persistent operation/journal status and crash-recovery guidance; a simple in-process lock is not a durable transaction.

**P1 — usability and maintenance:**

- **DONE in v0.5.4:** Integrated a read-only **Live energy flow** table and compact power/SOC graphics into the *separate* SAJ TOU Control card using existing Safe Monitor sensors. The original SAJ Energy dashboard and `saj_h2_safe` source remain unchanged. A built-in HA historical line graph is **not yet included**; the graphics show current comparative watts and SOC, not recorded 24-hour trends.
- **Verify on owner's browser** that source sensor values and mobile layout match expectations; absent/unavailable sensors should display "—", never invented zeros.
- Add browser interaction tests (time inputs, weekends, split overnight, one-confirmation popup, Save, fallback selection). CI currently only validates JS syntax.
- Update stale descriptions in `services.yaml`, `config_flow.py`, `docs/SAFETY_AND_ROADMAP.md`, `CHANGELOG.md`. Some are historical and should be marked archived rather than silently rewriting prior evidence.
- Fix any confusing “read-only” UI wording without breaking sensor unique IDs. Preserve older pilot service names only as backwards-compatible aliases until migrations are checked.

**P2 — explicitly requested future capability (not currently shipped):** on-demand charge/discharge with minutes and cancel/watchdog, OCPP EV charging, HVAC coordination, forecast/tariff automated optimisation, optional history visualization.

## 12. Handover instructions for the next developer or AI assistant

1. Read this guide first; read `tou_protocol.py`, `__init__.py`, `schedule_transaction.py`, `supervised_write.py`, `supervised_fallback.py`, `frontend/saj-tou-dynamic-card.js`. Use the archived development diary only when tracing the *historical source* of a mapping or decision.
2. **Inspect actual GitHub main and its CI** before editing; verify whether version numbers have advanced beyond 0.5.2. Do not claim this date/version is current forever.
3. If creating a new UI feature, **do not alter the separate `saj_h2_safe` repo or SAJ Energy**. Reuse its existing HA sensor states as read-only data sources.
4. Preserve exact model/firmware profile assumptions; never guess write register meanings beyond 0x3647/0x365F and known schedule layout.
5. Provide owner one concise copy-paste update command only after CI success; avoid asking previously answered questions.
6. Record whether a feature is coded, simulated, verified by real Modbus, or independently confirmed by elekeeper. They are **not equivalent**.
7. Keep all new user-visible text using **elekeeper** lowercase. Preserve a single confirmation popup for dangerous writes. Distinguish a *standby fallback* from *backup/off-grid operating mode*.
8. After meaningful commits, **update this handover** and entrypoint README; retain all historical facts and unresolved risks.

---

## 13. v0.5.4 combined dashboard: real Live energy flow data contract

The user shared the earlier SAJ Energy **Live energy flow** panel screenshot and explicitly requested those **graphics and 5-column table be combined with the advanced TOU controls**, *after* completing this full handover. Implementation is in `frontend/saj-tou-dynamic-card.js`, and this stays in the **SAJ TOU Control** sidebar; the separate read-only SAJ Energy dashboard is **not** edited.

The new section is **read-only**, above the control panes. It shows:

- A responsive, horizontally scrollable five-column table: **☀️ Solar | 🏠 House | 🔋 Battery | ⚡ Grid | 🔮 Forecast**.
- Rows for current W/kW, generating/using/charging/discharging/import context, SOC + estimated stored kWh, grid export W, today's total solar outlook, forecast remaining today and tomorrow.
- Compact *relative instantaneous-power bars* for Solar, House, Battery magnitude and Grid magnitude. These **are not historical charts**, nor an assertion of actual physical energy route.
- Separate battery SOC progress bar and estimated stored energy.
- Device mode/flow summary and warnings that grid polarity remains provisional and forecasts are estimates.
- Clean "—" placeholders when read-only sensors are missing/unavailable; the chart must never hallucinate measurements.
- Energy value updates refresh **only** the energy section when TOU device config is unchanged; avoid discarding or unfocusing an in-progress time input/local draft.

**Source entity IDs** are grounded in the separate safe monitor's existing `dashboards/saj-energy.yaml`. Defaults:

| Metric | HA entity |
|---|---|
| Solar watts | `sensor.saj_h2_safe_monitor_total_solar_power` |
| House watts | `sensor.saj_h2_safe_monitor_home_consumption` |
| Battery signed watts | `sensor.saj_h2_safe_monitor_battery_power` |
| SOC | `sensor.saj_h2_safe_monitor_battery_state_of_charge` |
| Stored energy estimate | `sensor.saj_h2_safe_monitor_estimated_battery_energy` |
| Grid import provisional | `sensor.saj_h2_safe_monitor_grid_import_direction_unverified` |
| Grid export provisional | `sensor.saj_h2_safe_monitor_grid_export_direction_unverified` |
| Today measured+remaining outlook | `sensor.saj_h2_safe_monitor_today_s_solar_outlook_actual_remaining` |
| Remaining forecast today | `sensor.saj_h2_safe_monitor_solar_forecast_remaining_today` |
| Tomorrow's forecast | `sensor.saj_h2_safe_monitor_tomorrow_s_solar_forecast` |
| Safe monitor mode label | `sensor.saj_h2_safe_monitor_operating_mode` |

**Battery power sign** from read-only monitor: **positive = discharging**, **negative = charging**. Treat near-zero magnitude as idle. Grid sign has not been independently paired at nonzero import/export, so the UI explicitly labels direction as provisional. Forecast numbers are not controls and are subject to weather/model uncertainty.

**Current limitations:** exact default entity IDs may change if user has manually renamed sensors; if optional Safe Monitor sensors are absent, visualize available values and display "—" for others. This feature should remain *optional* and must never prevent TOU controls from loading. A true recorder-backed 24-hour history graph would require its own tested implementation and is not implied by these instantaneous power bars.

## 14. v0.5.4 visual redesign — annotated owner feedback

Owner reviewed the combined energy/TOU screenshot and marked out duplicate headings and the redundant selector, and circled the two separate Mode and Outside-TOU cards with a large **“Join”** annotation. The explicit intent is **a cleaner unified control panel**, not changing Modbus semantics.

Changes to `frontend/saj-tou-dynamic-card.js`:

- The Home Assistant dashboard already has **Time of Use** as a native navigation header. Removed the card's duplicate **Battery time-of-use** heading and **Mode & schedule control** badge. The native HA view title is not manipulated by JS.
- Hid the **Detected TOU device** chooser when only one TOU integration is present; if multiple integrations are detected, a compact **Inverter** selector still appears. Auto device discovery and source entity mapping remain unchanged.
- Replaced the two neighbouring standalone panes with one full-width, rounded **Inverter controls** section. Operating mode and Outside TOU windows appear as aligned **columns within one border**, separated by a subtle internal divider. On narrow screens they stack vertically.
- Improved selected mode-button contrast even while disabled (already active), richer tabular readings and softer spacing, captions, responsive energy bars and saved schedule action emphasis.
- Refined read-only **Live energy** table with larger numerical values, subdued header row, better border rhythm, thin relative power bars, and legible SOC. Did not modify or reconnect `saj_h2_safe` or existing SAJ Energy dashboard.
- Added a clear schedule section title and visually distinguished the primary **Save schedule changes to inverter** button.
- **No Modbus register addresses, service commands, authorization prompts or write paths were changed in this styling release.**

**Verify on the owner's browser:** one configured device should show no redundant chooser, one unified controls panel, readable energy data, responsive stacking on mobile, and unchanged mode/fallback/schedule functions. Existing unsaved drafts, selected statuses, Standby confirmation and stale-readback rules remain in effect.

## 15. v0.5.5 native dashboard title and device selector — owner request

**User request:** In the screenshot the top Home Assistant navigation title said **Time of Use**. Replace that with a device-oriented name such as **SAJ H2 Control**. When more than one SAJ inverter exists, present a chooser in the same general header area, not buried inside the schedule table.

**Implemented:** Existing and newly generated Lovelace views use **SAJ H2 Control** in the native Home Assistant header. Since a custom Lovelace card does **not** have a supported API to inject interactive controls into Home Assistant's global navigation toolbar, the multi-inverter chooser appears as the **first row immediately underneath** that native toolbar, and only when multiple compatible SAJ TOU devices are detected. A single inverter has **no redundant selector**.

**Migration:** The one-off helper `dashboard_title.py` has a pure `migrate_generated_view_title(config)` function. On integration setup the frontend code checks the existing storage dashboard at path `saj-tou-control`, calls `LovelaceStorage.async_load(False)`, and saves a copy with a single view-title change **only** for exact old autogenerated configuration (dashboard title `SAJ TOU Control`; exactly one panel view `tou`; view title `Time of Use`; sole card `custom:saj-tou-dynamic-card`). No additional card, dashboard, sidebar title, entity ID or URL path is modified. If user altered their view title or cards, migration skips it. The migration is idempotent; reruns do not rewrite. New dashboards are created with title `SAJ H2 Control` from the outset. This uses Home Assistant's Lovelace storage API, not direct editing of `.storage` JSON.

**Multi-device selection:** Dynamic card uses `findDevices(hass)` and exact `saj_tou_entry_id` per group, readable HA friendly names, duplicate disambiguation `Device 1/2/...` and a labelled native HTML select. Selecting a different device resets transient success/error messages and keeps per-device local draft records isolated; all backend calls continue passing the correct `entry_id`.

**Tests:** `tests/test_dashboard_title.py` covers one-view title migration, idempotency, invalid configs, preservation of other fields, and refusal to overwrite customized layouts; added to CI. JS syntax checks also run. **Still to verify:** the user's currently installed dashboard must be restarted/reloaded once to see the migration and selection UI. Other older or customized dashboards may require the user to rename the view title manually using Home Assistant's dashboard editor. v0.5.5 introduces no new Modbus writes or hardware risks.

## 16. v0.5.6 visual alignment and release numbering policy

**Owner's specific version policy:** Keep all iterative releases **below v1.0.0**, advancing with small patch numbers (e.g. **0.5.6 → 0.5.7**) instead of jumping to v0.6 or v1 before the project is actually stable. **v1.0.0 is reserved for the final stable version** after on-device verification and sufficient polish. Do not call patch changes “final”.

**Screenshot reference (2026-11-02):** The owner supplied a dark UI screenshot explicitly showing one “Inverter controls” header bar, **Refresh inverter state on the far right of that header**, and two side-by-side cells, Operating mode and Outside TOU windows. Their active device states are inline with each section heading; beneath them are the two mode buttons and fallback dropdown. Their prior v0.5.5 screenshot was less aligned and displayed Refresh underneath mode buttons.

**Implemented in the custom card v0.5.6:**
- Moved the same existing **Refresh inverter state** action into the shared header. The callback still uses the read-only refresh service. Disabled while concurrent inverter commands or another refresh are in progress.
- Made each cell's heading and current device value a single compact horizontal row, which wraps on smaller screens. Both panels remain inside one rounded card with a subtle divider; narrow screens stack.
- Refined section rhythm, muted descriptions, selected-mode contrast, dropdown/button heights, hover/focus-visible treatment, and device state typography. Preserved accent colors through HA CSS variables and small conservative fallbacks.
- Kept existing Standby confirmation, mode and schedule service calls, masks, readback freshness requirements and source-of-truth behaviour unchanged; **this is a UI-only patch**.
- Frontend resource cache-bust version **`/saj-h2-tou/v056/saj-tou-dynamic-card.js`**. Backend manifest v0.5.6.

**Testing/limits:** GitHub CI validates JavaScript syntax and Python tests. The appearance must still be viewed in the owner's actual Home Assistant browser. No simulated test represents a live inverter command. Do not change the user-specified layout in future releases without referring to the screenshot and this requirement.

## 17. v0.5.7 energy UI, dark fallback dropdown, and top data refresh

**Owner screenshots / requests (2026-11-02):** Windows/Brave rendered the native Outside TOU HTML select popup with a white background and poorly contrasted text. The combined Live energy table was too tall and not visually dense enough. User supplied compact reference with battery SOC first, four power bars and the five-column energy table below. Additionally, they explicitly asked for a **REFRESH/RELOAD DATA** icon/button beside the top "Last verified" timestamp.

**Implemented UI:**

- Native fallback `<select>` replaced by an **accessible dark in-card menu**, styled within this card's shadow DOM. The trigger has `aria-haspopup=listbox` and `aria-expanded`; the options have `role=option` and `aria-selected`, plus keyboard Escape and ArrowDown/ArrowUp/focus handling. Selected option and popup theme remain dark regardless of OS-level native dropdown rendering. The same backend `supervised_outside_tou_fallback` is called; selecting Standby continues to show **one** warning popup. Real device state is authoritative; the menu doesn't pretend a write succeeded.
- Live energy reordered to **battery SOC with mode label**, then four **instantaneous power bars** (Solar, Home, Battery magnitude, Grid magnitude), then the five-column **Solar / House / Battery / Grid / Forecast** table. Reduced spacing, simplified read-only forecast disclaimer and removed a repeated grid/mode summary line. Grid table now shows either provisional import or export status instead of always labelling zero watts “Import”; grid power value uses whichever absolute direction is available.
- A compact `⟳ Refresh / reload data` button appears **beside Last verified** at the very top. Existing redundant control-panel refresh button was replaced by a plain panel subtitle to avoid two actions for the same task. The button is disabled while busy or during a write/validation.
- User-triggered refresh is **read-only**. It invokes `saj_h2_control_enhanced.preview_mode_change` for a fresh TOU coordinator read, then calls Home Assistant's built-in `homeassistant.update_entity` on **at most one** representative Safe Monitor live sensor (solar/home/battery/SOC) and **one** forecast sensor. The Safe Monitor uses separate coordinator instances for live Modbus and forecasts. This prevents redundant update requests for every individual monitor sensor and preserves its read-only implementation. No command to change solar, battery or TOU settings is sent by refresh.
- The top status line displays a concise refresh-in-progress/success/partial-failure message, without falsifying the Last verified timestamp. Original readback remains authoritative and changes as updated HA states arrive. Unsaved schedule drafts are not discarded by refreshing.
- CSS remains dark, uses HA theme variables and responsive wrapping. Live data **keeps polling independently**; manual refresh is an extra request, not a replacement for normal updates.

**Safety/test status:** No backend Modbus write semantics, confirmation phrases, writable registers, hardware protections or separate `saj_h2_safe` code changed in this release. GitHub CI checks JS syntax and existing simulated backend tests. **The in-browser popup appearance and actual HA update_entity refresh must be visually/live checked by the owner; CI is not a browser test or a real inverter test.** If update_entity fails, the card reports a partial refresh; do not show a false success.

**Version policy:** Continue only patch increments `0.5.7 → 0.5.8` and reserve `1.0.0` until stable and hardware-verified.

## 18. v0.5.8 minimal header cleanup

Owner explicitly requested removal of the redundant **“● Read-only telemetry”** badge from the top-right of the Live energy section, shown crossed out in their screenshot. The card now renders the Live energy heading and category subtitle without any redundant badge. All numerical readings, source sensors, inverter controls, single-confirmation workflows, refresh action and Modbus write logic remain unchanged. Frontend URL cache-busted to `/saj-h2-tou/v059/saj-tou-dynamic-card.js`. Reserve v1.0.0 for final stability; continue 0.5.x patches.

## 19. v0.5.9 Live energy update cadence caption

Owner asked to show how frequently the live energy readings refresh after reviewing the clean v0.5.8 layout. The Live energy title row now contains a small **↻ Updates ~10 sec (default)** text label (not a separate badge). This reflects the separate safe monitor's `live_scan_interval` default of 10 seconds; the interval may be configured, and solar forecast updates are independent. The label has a tooltip explaining both limitations. This is **display-only**. No polling rates, sensor processing, dashboard refresh action, write controls, or other integrations were altered. Frontend cache URL is `/saj-h2-tou/v059/saj-tou-dynamic-card.js`; release v0.5.9. Browser visual verification remains needed.

## 20. v0.5.10 final screenshot polish and GitHub-only no-YAML distribution

### Owner's explicit requirements

On 2026-11-02 the user supplied two annotated screenshots and requested:

1. In the **Inverter controls** header, remove the meaningless static text **“Live mode · Outside TOU”** and **show actual live values instead**. Both section bodies repeated these same values as **“Device: Self-consumption”**; move them to the unified header for a clear at-a-glance summary.
2. Condense the bottom **Charging & discharging schedules** layout. The two 0/7 cards repeated counts in header and badge, spread their empty state vertically, and showed a large always-on paragraph about validation, weekend bits, midnight, partial writes and approximate power. Shorten the cards, make controls discoverable, and make the warnings less intrusive without concealing risk.
3. Make this a real repo-ready, updateable integration **from GitHub alone, without manual `configuration.yaml`, Lovelace YAML, or JS resources**, with complete install/update instructions and durable developer handover. The independent Safe Monitor and existing **SAJ Energy** dashboard must remain untouched.
4. Preserve the version policy: **0.5.x patch releases until genuinely stable; 1.0.0 reserved for a fully field-verified final version**.

### Completed in v0.5.10

**Live Inverter controls summary.** The card now renders a right-aligned, compact two-value **Operating: [current HA operating mode]** and **Outside TOU: [current HA fallback state]** header, both sourced directly from the integration's latest Modbus-read sensors. The redundant static pill and two separate “Device: …” captions have been removed. The mode buttons and fallback selector remain beneath their respective clear headings in the existing two-column panel. Status values change only as readback states change, not as speculative optimistic writes.

**Condensed schedule section.** Section heading **Charging & discharging** shows a compact “7 slots available per direction” descriptor or **● Unsaved changes** indicator; each charging/discharging panel has a **n/7** count and an **+ Add charging/discharging** button *in its top row*. Removed duplicate “configured on inverter” count badges and empty-state buttons below the text. For empty schedules, only a short **No charging/discharging periods set** line is shown. Saved slots retain all time/day/%/estimated W controls. The footer has **↶ Reload from inverter** on the left and the primary **Save schedule changes to inverter** on the right. A concise line below notes that power W is estimated, that saves verify, and that interrupted writes require manual elekeeper inspection. **Important risks still appear in the actual Save confirmation modal and error responses; no safety check was removed.**

**UI-owned, no-YAML installation.** Repo root now has `hacs.json` (name **SAJ H2 Control Enhanced**), valid one-integration layout, and [`docs/INSTALLATION.md`](docs/INSTALLATION.md). For HA versions supporting HACS/Marketplace custom integration repositories, users add **this exact GitHub repository** and install, then use **Settings → Devices & services → Add integration**. The integration config flow takes an existing read-only monitor source or manually entered Modbus host/port; it automatically registers `saj-tou-dynamic-card.js` via Home Assistant's frontend and creates a standalone **SAJ TOU Control** dashboard with the native **SAJ H2 Control** view title. It does **not** need `configuration.yaml`, custom Lovelace YAML, or a manual frontend JS resource.

**Bundled monitor / HACS constraint (2026-11-02):** All monitor source is included under `bundled_components/saj_h2_safe` in **this repository** and `scripts/install.sh /path/to/config` installs it by default if absent, preserving existing monitor files. Do **not** direct users to the independent monitor repository or mention obsolete `--with-safe-monitor` flag. HACS installs only `custom_components/saj_h2_control_enhanced`, so standard HACS alone does not deploy the bundled monitor on a new system. Recommend the one-command installer for a complete Linux/Docker deployment. Each HA integration domain still needs its own config entry; existing entries are preserved. See `docs/INSTALLATION.md`.

**Further offline installer verification:** `tests/test_install_script.py` runs the actual shell installer against a fake GitHub archive and temporary HA configuration directory. It tests first installation of both components, reinstallation and backup of changed control code, **preservation of an existing Safe Monitor**, exact source folder placement and unchanged `configuration.yaml`. Included in the passed CI run linked above. This is still not a physical HA environment test or an actual inverter read/write test.

**Included one-repo CLI installer.** `scripts/install.sh /path/to/homeassistant/config [--control-only]` downloads **this repository only**, backs up existing controller code under `.saj-h2-backups/` (outside `custom_components/`), and updates control code. By default it also installs bundled `saj_h2_safe` if absent; if present, its code is left untouched. `--control-only` skips monitor installation. Users restart HA and configure Safe Monitor (if needed) and the controller via HA Settings → Devices & services. No YAML edits or second repository needed. Script does not silently create config entries or change inverter settings.

**Corrected new-entry title:** `config_flow.py` no longer creates new control config entries titled **“(read-only)”**; now **SAJ H2 Control Enhanced**. Existing config entry IDs and previously installed sensor unique IDs are not migrated or removed. `__init__.py` / `frontend_setup.py` comments now accurately describe current control behavior.

**CI:** New `tests/test_package_and_ui.py` verifies `hacs.json`, one integration folder, config flow, bundled frontend, versioned URL matching manifest, automatic Lovelace creation, and screenshot-requested concise UI/status content. Workflow now checks this suite and `bash -n scripts/install.sh`. The obsolete “Reject Modbus write implementations” grep, written for an earlier planning-only project and incapable of describing the real supervised write paths, has been retired. The **existing simulated** readback, mode, schedule, fallback and title migration tests continue running. **No CI test connects to the owner's inverter or executes an end-to-end browser/HA session**.

### Remaining limitations (do not call v1 stable yet)

- New v0.5.10 layout still requires screenshot validation on the owner's browser; GitHub JS syntax and packaging tests are not equivalent to a browser visual regression test.
- Tested model/profile is still SAJ **H2-10K-S3-A, control firmware v2.018**; writes are intentionally not universally enabled for arbitrary SAJ models or firmware.
- The first full broad 7+7 schedule write, Standby fallback write and all Sat/Sun individual bit combinations lack complete owner-confirmed live-hardware evidence. Old user screenshots show the app's current saved schedule and some completed operations but are not comprehensive certification. **Never blindly repeat or rollback an ambiguous write.**
- The standalone Live energy graphs require the separate Safe Monitor to expose its existing HA sensors. The new installation guide is self-contained and can bootstrap the monitor code, but **automatic entity/config creation is not promised** for a missing monitor; each integration is configured through HA's normal UI.
- HACS/Marketplace behavior changes between HA releases; `hacs.json` and repo structure follow the current publisher format but cannot guarantee approval in the official catalog. Custom repository support varies by installation. The shell script is the documented fallback and **does not edit HA YAML**.
- Future force-charge timers, OCPP, HVAC automations, 24-hour recorder charts, persistent cross-reboot write journal, and broad hardware compatibility are not yet shipped.

### Next developer checklist

1. Run the complete GitHub CI and verify the manifest tag **0.5.10** matches frontend cache asset **`/saj-h2-tou/v0510/saj-tou-dynamic-card.js`**.
2. Follow **docs/INSTALLATION.md** on a fresh HA test instance using only this repository (with its bundled Safe Monitor). Confirm custom repository installation, Settings → Devices & services config flow and automatic dashboard/card creation **without any YAML edits**.
3. Verify single-device and multi-device headers show the correct **Operating / Outside TOU** values from distinct readbacks. Ensure switching devices never sends a write.
4. Verify empty schedule panels have the add button in their header; edited drafts show a marker; Save still uses one confirmation and does complete preflight/post-write checks.
5. Record actual on-device confirmation for remaining unverified schedule/fallback write combinations and document device firmware and elekeeper evidence before considering v1.0.0.
6. Keep the separate `saj_h2_safe` integration and old SAJ Energy dashboard **unchanged**.

## 21. v0.5.11 — self-contained Safe Monitor bundle and easiest installation

**User requirement (2026-11-02):** No instructions that send users to a second GitHub repository to obtain required Live energy monitoring. **Every required code file must live in `userdc-dev/saj-h2-control-enhanced`** and installation should prominently offer the short copy-paste shell command used for the owner's Kamrui system.

### Authoritative source layout

- `custom_components/saj_h2_control_enhanced/`: existing controller, Modbus TOU services, frontend card, config flow, dashboard registration and settings readback.
- `bundled_components/saj_h2_safe/`: **complete, local snapshot** of the read-only SAJ H2 Safe Monitor: `__init__.py`, `config_flow.py`, `const.py`, `manifest.json`, `sensor.py`, `solar_forecast.py`, `solar_model.py`. This has the same `saj_h2_safe` HA domain, so existing sensor IDs and HA automations remain compatible. Do not rename the domain, and never overwrite already-installed monitor code. This is the actual monitoring/forecast code, not an online link or a placeholder.
- `scripts/install.sh`: downloads **one archive of this controller repository**, copies bundled monitor `bundled_components/saj_h2_safe/` to `custom_components/saj_h2_safe/` **only when missing**, and installs/updates controller `custom_components/saj_h2_control_enhanced/`. Before replacing controller code, backs up old code to `<HA_CONFIG>/.saj-h2-backups/` outside `custom_components/`. `--control-only` is the optional skip-monitor flag; `--with-safe-monitor` is obsolete and must not appear in current instructions. Installer never executes Modbus writes, edits YAML, deletes entities or restarts HA on its own.
- `docs/INSTALLATION.md`: contains both the owner's exact copy-paste command and generic installation instructions. It explains first-time setup of the **two separate HA config entries** (monitor, controller) through Settings → Devices & services, no YAML or JS resources required. Controller auto-creates the dashboard after HA restart and config flow.

### Single command for existing Kamrui deployment

```bash
curl -fL https://raw.githubusercontent.com/userdc-dev/saj-h2-control-enhanced/main/scripts/install.sh -o /tmp/install-saj-h2.sh &&
bash /tmp/install-saj-h2.sh /home/kamrui/compose-files/homeassistant/config &&
docker restart homeassistant
```

For any other installation change the HA config path and use its own HA restart mechanism. Users should review any downloaded script before execution. This installs code from only this GitHub repository; no second GitHub source is fetched at runtime.

### Why keep two HA domains?

Existing `saj_h2_safe` entities already feed the Live energy chart and may be referenced by the owner's other dashboards, energy statistics and automations. Moving their sensor IDs into the controller domain risks breaking that system. **Packaging both from one GitHub source does not require merging them into a single HA config entry.** New users configure each bundled component through HA's UI once; upgrades preserve all existing entities/config entries.

### HACS limitation explained accurately

The root `hacs.json` makes the **controller** installable as a HACS custom Integration repository. HACS normally copies **only one `custom_components/<domain>` integration folder**, not a second independent `bundled_components/` tree. Therefore **HACS-only installation is not a full first-time Live energy installation**; recommend the one-command script above for complete deployments or copying both folders from this repository through supported file management. This is a HACS limitation, not a missing external dependency. No other GitHub repository is needed.

### Regression tests and release policy

- `tests/test_install_script.py`: runs the actual installer offline using **one simulated repository archive**, verifies first install of **both** integrations, preservation of existing Safe Monitor, backup of controller before update, no external repo URL and no change to `configuration.yaml`. It also rejects obsolete `--with-safe-monitor` flag.
- `tests/test_package_and_ui.py`: checks all bundled monitor files, root HACS/main integration layout, frontend version parity and that the installer refers to the bundle rather than a second download.
- CI: Python compile, JS syntax, simulated Modbus write/readback safety, installer shell syntax, and the offline install tests. **These are not proof of live inverter compatibility.**
- Current version is **0.5.14** and frontend cache-bust is `/saj-h2-tou/v0514/saj-tou-dynamic-card.js`. Earlier v0.5.11 packaging release details are preserved above. Reserve **v1.0.0** for completed hardware validation.
- **No changes** to the existing control write services, Modbus register mappings, permissions, confirmation dialogs or the user's current Safe Monitor installation were needed for this packaging release.

**Historical appendix:** The full earlier handover is retained unabridged at [docs/DEVELOPER_HANDOFF_HISTORY_THROUGH_V040.md](docs/DEVELOPER_HANDOFF_HISTORY_THROUGH_V040.md); it contains original 2026-11-01 experiments, paired screenshots, previous mode-control iterations, firmware discovery, dashboard cache fixes, and repeated user feedback. Its early “planning-only” language was true at the time but is no longer a current feature status.
