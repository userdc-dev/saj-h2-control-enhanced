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

**4. Wait for Recorder and statistics.** New energy entities do not retroactively recreate past totals. If a sensor is not listed, verify **Settings → System → Repairs → Statistics** (or **Developer tools → Statistics** depending on HA version), available entity state, statistics compatibility and Recorder inclusion. Do not add the same original meter and its duplicate alias to Energy together: this would double-count energy.

### Critical distinction: grid estimates vs electricity meters

**Grid import/export kWh are conservative estimates from existing signed grid *power* samples**, not the SAJ lifetime grid sell/feed-in registers, because the latter's direction has not been independently verified. The default inferred convention is positive grid power → imported, negative → exported. The integration integrates only consecutive valid readings (up to 60 seconds apart), handles a sign crossing without cancellation, records hourly/day/month counters, persists state across restarts, and leaves missing intervals unaccounted. These values do not reconstruct energy measured before installation and are **not utility settlement data**.

**Before selecting these estimated grid kWh sensors for your Energy dashboard, compare a sustained import and export condition against the utility meter and verify the sign convention.** Otherwise the estimate could reverse imports and exports. Prefer a verified smart-meter energy counter or retailer feed if you have one.

For the native SAJ lifetime **solar** and **battery** energy counters, compare at least a few readings against the official SAJ app/elekeeper before relying on them as authoritative; the register mapping has not been universally validated for all SAJ firmware models.

## B. Electricity cost estimates

Open the **Costs & savings** tab inside **SAJ H2 Control** (also accessible from the compact Cost estimates panel on Energy & controls).

Set **three signed static rates** in the HA-configured currency:

- **Import cost per kWh** — positive = customer pays; negative = customer *earns* by importing.
- **Export payment per kWh** — positive = customer receives credit; negative = customer pays a fee to export.
- **Daily supply charge** — normally positive; negative values are supported for unusual rebates.

Defaults are **illustrative only** (import 0.35, export 0.05, daily 1.00, normally AUD on Australian systems). Until the user confirms pricing, dollar totals are not displayed. Cost settings are stored in the *control integration config entry*, not in YAML. Changing these rates **never** modifies inverter TOU registers or battery controls.

Net estimated customer cost:

```
grid imported (kWh) × signed import cost
 - grid exported (kWh) × signed export payment
 + daily supply rate × recorded-coverage hours / 24
```

A positive result indicates net expense, a negative result indicates estimated net credit. Results are provided for **today** and **this calendar month**, strictly over available recorded intervals. The supply charge is prorated by recorded coverage rather than pretending an entire day was monitored. An actual bill can include demand charges, taxes, discounts, billing cycles, separate TOU rate periods, distributor adjustments and other items that the flat model does not represent.

### Solar and battery estimated benefit

The dashboard shows a **combined illustrative self-supply and export value** using monitored home-demand energy and inferred grid imports/exports:

```
max(0, monitored house demand kWh − monitored grid import kWh) × import cost
 + monitored export kWh × export payment
```

The optional **battery discharge potential** is discharge kWh multiplied by import cost. **Do not add battery potential to combined self-supply benefit**; it overlaps, ignores charging cost/losses, and might represent grid-charged energy. These figures are not auditable component-by-component savings or counterfactual bill guarantees. Negative tariffs can produce a negative estimated benefit: do not clamp the monetary results to zero.

### Future live prices

This release has **static rates only**, explicitly editable in the UI. Dynamic pricing from AEMO/retailers, separate import/export TOU bands and historical tariff re-pricing are future work. Do not claim a live AEMO connection or automatically apply public wholesale prices to a customer's retail tariff.

## C. Forecast learns from actual observations

The editable Solar forecast coordinator now watches existing **read-only solar power and battery SOC** reports and stores its hourly correction factors under HA storage. It only learns a completed hour when at least **45 minutes** of reliable observed samples exist, forecast expected energy is **at least 0.7 kWh**, reported cloud cover is **25% or less**, and battery SOC has not reached **97%** (possible curtailment). A slow weighted factor adjustment is clamped between **0.65× and 1.15×**. Per-hour factors survive restarts and are reset when the underlying panel layout/efficiency settings change, so old calibration is not blindly applied to a new system.

This model **does not backfill past days prior to installation** and cannot reliably separate cloud-model errors, shade, solar curtailment and external VPP actions. It does **not** adjust inverter operating modes or write battery registers.

## D. Safety, maintenance and limits

- Existing mode controls, 7+7 TOU schedules, verified readback and confirmation gates remain unchanged.
- The cost/forecast/energy integration is strictly read-only; there is no automatic TOU strategy or AEMO control.
- Backup code before updates, verify existing entity IDs, and restart HA normally. Existing `saj_h2_safe` code is preserved by the bundled installer.
- For separate grid calibration, service prices, multi-inverter monitoring or non-flat seasonal plans, extend the backend with explicit tests and configuration rather than guessing signs or rewriting historical counters.
