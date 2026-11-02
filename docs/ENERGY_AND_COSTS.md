# Home Assistant Energy and Costs & savings — no YAML

**One repository:** `userdc-dev/saj-h2-control-enhanced`. The read-only monitor `saj_h2_safe` ships in `bundled_components/`; the controller reuses an existing *configured* monitor entry on the **same inverter IP**. It never overwrites existing monitor code, changes historical entities or sends Modbus writes for energy/cost functions.

## A. Home Assistant Energy setup

**1. Install or update** using the supported `scripts/install.sh` installer (see [INSTALLATION.md](INSTALLATION.md)). Configure **SAJ H2 Safe Monitor** first under **Settings → Devices & services** if it is not already configured, then **SAJ H2 Control Enhanced** with the same inverter host/port. Existing entries should be reused; do not remove, rename or recreate your existing monitor.

**2. Locate the new easy-to-read sensors:** open **Settings → Devices & services → SAJ H2 Control Enhanced → Entities**, or **Developer tools → States** and search their friendly names. These are new aliases with stable unique IDs, so the original Safe Monitor sensors and existing dashboards are retained.

**3. Configure Energy:** **Settings → Dashboards → Energy**; choose the values under their matching categories:

| Energy setup field | Choose this new entity name | Measurement and readiness |
|---|---|---|
| Electricity grid → Grid consumption | **Grid energy imported • estimated** | Total-increasing **kWh**, integrated only when the HA monitor is running; grid polarity *unverified* |
| Electricity grid → Return to grid | **Grid energy exported • estimated** | Total-increasing **kWh**; same provisional polarity/coverage |
| Electricity grid → Type of power measurement → **Standard** | **Grid power • signed (import + / export −)** | Instantaneous **W**, single signed power source; use only after verifying polarity |
| Electricity grid → Type of power measurement → **Two sensors** → Power imported from grid | **Power imported from grid • provisional** | Instantaneous **W**, import-only positive readings |
| Electricity grid → Type of power measurement → **Two sensors** → Power exported to grid | **Power exported to grid • provisional** | Instantaneous **W**, export-only positive readings |
| Solar panels → Solar production energy | **Solar production energy • total** | Native SAJ lifetime total **kWh**, not a power sample |
| Solar panels → Solar production power | **Solar production power** | Current **W**; `device_class: power`, `state_class: measurement` |
| Solar production forecast | **Editable solar forecast** | PV **kWh** forecast on Solar forecast tab; **not** a measured cumulative energy counter; don't select as the production meter |
| Home battery → Energy going into battery | **Battery energy charged • total** | Native SAJ lifetime charged **kWh** |
| Home battery → Energy coming out of battery | **Battery energy discharged • total** | Native SAJ lifetime discharged **kWh** |
| Home battery → State of charge | **Battery state of charge** | Current **%**, battery measurement state class |
| Home battery → Power measurement (when offered) | **Battery power • signed** | Current **W**; positive = discharging, negative = charging |
| Home consumption energy (optional elsewhere) | **Home energy consumed • total** | Native SAJ lifetime **kWh** |
| Home consumption power (optional elsewhere) | **House consumption power** | Current **W** |

In some HA versions Energy asks for just energy, in others you can also choose corresponding power measurements. Only the suitable sensors appear in each selector. Home Assistant requires energy kWh sensors with `device_class=energy` and `state_class=total` or `total_increasing`, power W sensors with `device_class=power` and `state_class=measurement`, and SOC as a battery percent measurement.

**Power measurement selector:** Home Assistant's Energy UI offers **No power sensor**, **Standard**, **Inverted** and **Two sensors**. Recommended choices for the current provisional SAJ convention: (a) **Standard** with the new **Grid power • signed (import + / export −)** sensor, or (b) **Two sensors** with the dedicated **Power imported from grid** and **Power exported to grid** aliases. **Inverted** is ONLY for a confirmed reverse-polarity signed sensor; do not select it speculatively. The two-sensor option uses non-negative import/export watts and is often easier to interpret. Do not configure both options simultaneously. In all cases, validate readings against your actual utility meter; the integration cannot certify the grid polarity.

**4. Wait for Recorder and statistics.** New energy entities do not retroactively recreate past totals. A power sensor is a recorded **W measurement**, not a cumulative kWh total. The new aliases have `device_class: power` and `state_class: measurement`; HA must record their numerical states for at least one 5-minute statistics cycle before the **Select a statistic** dropdown can use them. If a sensor is not listed, verify **Settings → System → Repairs → Statistics** (or **Developer tools → Statistics** depending on HA version), available entity state, statistics compatibility and Recorder inclusion. Do not add the same original meter and its duplicate alias to Energy together: this would double-count energy.

### Critical distinction: grid estimates vs electricity meters

**Grid import/export kWh are conservative estimates from existing signed grid *power* samples**, not the SAJ lifetime grid sell/feed-in registers, because the latter's direction has not been independently verified. The default inferred convention is positive grid power → imported, negative → exported. The integration integrates only consecutive valid readings (up to 60 seconds apart), handles a sign crossing without cancellation, records lifetime/day/month counters, persists state across restarts, and leaves missing intervals unaccounted. These values do not reconstruct energy measured before installation and are **not utility settlement data**.

**Before selecting these estimated grid kWh sensors for your Energy dashboard, compare a sustained import and export condition against the utility meter and verify the sign convention.** Otherwise the estimate could reverse imports and exports. Prefer a verified smart-meter energy counter or retailer feed if you have one.

For the native SAJ lifetime **solar** and **battery** energy counters, compare at least a few readings against the official SAJ app/elekeeper before relying on them as authoritative; the register mapping has not been universally validated for all SAJ firmware models.

## B. Electricity cost estimates — full time-of-use tariff editor

Open **Costs & savings** inside **SAJ H2 Control**. You can configure:

- Multiple editable **import-rate categories** (Peak, Off-peak, Solar sponge and any custom category) with **one or more time windows and selected weekdays** per category. Overnight periods work across midnight; uncovered times use an editable fallback import rate.
- **Standard export FiT time windows**, **special high/battery FiT time windows**, and a separate export fallback. Standard FiT applies outside qualifying high windows by default; define explicit standard windows if your retailer plan requires them.
- Positive or negative prices for every import and export category, plus positive or negative daily supply charges.
- Separate **GST percentage** (included or extra), taxable import/export/supply checkboxes, and an optional **signed percentage extra levy or rebate**.
- **High FiT eligibility**: if the special FiT is contractually available to all exports in a window, apply it. If **battery-only**, don't claim eligibility without a verified energy-origin meter: use standard FiT and show an uncredited *potential adjustment*.

**Full beginner-friendly instructions:** [TIME_OF_USE_TARIFFS.md](TIME_OF_USE_TARIFFS.md).

### Time-aware monetary accounting, not flat-rate multiplication

Electricity imports and exports are priced **per recorded short interval** using the matching local wall-clock window, weekday and tax treatment. Intervals are split across minute/window boundaries, midnight and daylight-saving changes. A tariff change applies prospectively; previously accrued monetary costs **are not recomputed** at the new rates. Recorded costs and energy counters persist across restarts.

**Full fixed daily supply charge:** This is posted **once per local calendar day** after a user has configured the tariff and accounting is running, independent of solar/grid telemetry coverage (e.g. a $1.49/day charge shows as $1.49 today even after only 20 minutes of data). Month-to-date counts each day charged; it does not assume that offline, untracked past days were billed. A tariff change during a day does not charge the supply fee twice; the rate for subsequent new days applies from the next tracked date. GST/extra levies are included according to the user's selected supply flags. Existing v0.5.16 current-day prorated supply charges are reconciled to the full day once, not doubled. This is still an estimated bill, not an exact retailer invoice.

Daily/month figures show **partial measured coverage** separately from **tariff-priced coverage**. Per-category kWh and monetary breakdowns help diagnose unexpectedly high/low costs. Missing past data is not backfilled or invented.

The combined self-supply/export value and battery-discharge potential are **illustrative and overlapping**, not independently measurable or additive. This is not a utility bill. **AEMO dynamic pricing is not connected**, and public wholesale rates should not be assumed equal to a household retail tariff.

## C. Forecast learns from actual observations

The editable Solar forecast coordinator now watches existing **read-only solar power and battery SOC** reports and stores its hourly correction factors under HA storage. It only learns a completed hour when at least **45 minutes** of reliable observed samples exist, forecast expected energy is **at least 0.7 kWh**, reported cloud cover is **25% or less**, and battery SOC has not reached **97%** (possible curtailment). A slow weighted factor adjustment is clamped between **0.65× and 1.15×**. Per-hour factors survive restarts and are reset when the underlying panel layout/efficiency settings change, so old calibration is not blindly applied to a new system.

This model **does not backfill past days prior to installation** and cannot reliably separate cloud-model errors, shade, solar curtailment and external VPP actions. It does **not** adjust inverter operating modes or write battery registers.

## D. Safety, maintenance and limits

- Existing mode controls, 7+7 TOU schedules, verified readback and confirmation gates remain unchanged.
- The cost/forecast/energy integration is strictly read-only; there is no automatic TOU strategy or AEMO control.
- Backup code before updates, verify existing entity IDs, and restart HA normally. Existing `saj_h2_safe` code is preserved by the bundled installer.
- For separate grid calibration, service prices, multi-inverter monitoring or non-flat seasonal plans, extend the backend with explicit tests and configuration rather than guessing signs or rewriting historical counters.
