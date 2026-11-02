# Time-of-use electricity tariffs — SAJ H2 Control Enhanced

This feature is **read-only electricity cost estimation** and does not command the inverter. All software needed is included in **this GitHub repository**. The original SAJ H2 Safe Monitor and the existing TOU/7+7 inverter-control functions are preserved.

## Set up your electricity plan

Open **SAJ TOU Control → Costs & savings → Your time-of-use electricity plan**. The default values are illustrative examples — **not your retailer contract**. You must review and save the correct numbers before trusting dollar estimates.

### 1. Grid import (electricity bought)

Enter **Other / fallback** (cost per kWh) to cover every unassigned period. Add or edit as many as **12 import categories** (for example Peak, Off-peak, Solar sponge, Super off-peak or Free power), with up to **24 individual windows per category**. Each window has:

- **Start** and **end** in 24-hour HH:MM.
- Weekdays: choose Monday–Sunday individually or use **Every day**, **Weekdays**, **Weekend**.
- Multiple periods can share a category, e.g. morning Peak 07:00–09:00 **and** evening Peak 17:00–21:00.
- If start time is later than end time (e.g. 21:00–07:00), the interval wraps to the following day. Weekday selection refers to the day the period **starts**.
- Import categories must **not overlap on the same local day/time**. Save validates this and displays an error; unassigned gaps automatically use the fallback price. An exact start or end timestamp belongs to only one band.

**Example only** (change to match your actual contract):

| Import category | Time windows | Price |
|---|---|---|
| Peak | 07:00–09:00 and 17:00–21:00 every day | +0.52 per kWh |
| Off-peak | 21:00–07:00 next day | +0.24 per kWh |
| Solar sponge | 10:00–15:00 | +0.12 per kWh |
| Other / fallback | Remaining hours | +0.35 per kWh |

Prices are in your HA configured currency. **Negative import prices are supported**: a negative cost means you are paid for importing electricity. All bands and the fallback can be negative, zero or positive.

### 2. Grid exports: standard and special high FiT

Enter three signed FiT rates: **Standard**, **High / battery special**, and **Other export fallback**. Positive FiT means **you receive a payment**; negative FiT means **you pay to export**.

- Add zero or more **Standard FiT** windows, with their own weekdays and times. With **no standard windows**, the standard FiT covers every time not qualifying for the high rate. If you specify standard windows, then unassigned hours use the **Other export fallback**.
- Add or remove **special high-FiT** windows and choose their days/times. These may overlap import windows since import and export are priced independently.
- In a special high-FiT window, choose **one** eligibility rule:
  - **All exports during this period qualify (retailer confirmed)**: the special FiT is applied to actual recorded grid export energy in this period.
  - **Battery-only / source not verified (safer default)**: the system cannot prove whether exported energy came from the battery rather than solar panels. It uses the standard FiT for estimated costs and separately shows the *possible difference* if all recorded exports were eligible. **Do not mistake potential for earned high-FiT revenue.**
- During a high-FiT window confirmed for all exports, **high takes precedence** over an overlapping standard export window. Otherwise an unverified special period conservatively uses standard FiT.

There is no automatic battery dispatch, export control or forced TOU charging in this feature.

### 3. GST, taxes and fixed charges

Set **Daily supply charge** (signed), **GST percentage** (0–100), **GST inclusive/exclusive**, **extra levy/rebate percentage** (−100 to +100), and checkboxes selecting whether GST / extra levy or rebate apply to **import**, **export**, and **supply** independently.

- **GST already included**: no GST added again to entered rates.
- **GST exclusive**: add GST on checked components.
- **Extra levy / rebate**: independently applied on top to selected components. Positive means an additional percentage; negative represents a discount/rebate.
- The export tax checkbox is **off by default**: most residential feed-in arrangements do not automatically include GST payable on exports. Check the actual contract, tax status and advice rather than assuming a particular tax treatment.
- Rates, supply charges and export credits can all be positive or negative. Taxes are computed against each signed line item, without rounding every 10-second observation.

> This is not a legal or tax determination. In Australia, retailer and consumer GST treatment may differ from the defaults, especially for registered businesses and special contracts. This estimator does not calculate separate demand charges, network penalties, meter fees, time-of-use tax thresholds, seasonal contract changes or concession eligibility.

## How time-of-use costs are calculated

The integration reuses the configured **read-only SAJ H2 Safe Monitor** and integrates signed grid power across short measured intervals (up to 60 seconds apart). It divides these intervals at **every minute boundary**, so rate changes, midnight, the start/end of a window and local daylight-saving transitions are handled without assigning an entire interval to the wrong tariff. When power crosses zero within one interval, import and export energy are split rather than cancelled.

**For each interval:**

```
Net customer cost
  = (imported kWh × active signed import rate + applicable taxes)
  − (exported kWh × eligible signed export FiT + applicable taxes/credits)
  + (daily supply × fraction of that local calendar day covered + taxes/credits)
```

Positive net cost = estimated expense; negative net cost = estimated credit. A 23-hour or 25-hour daylight-saving day uses its actual local calendar-day length for the supply-charge fraction.

The calculator **accrues actual measured-interval cost as readings arrive**. The *current* tariff does not reprice yesterday's electricity or earlier hours if you edit rates; changes start a new rate revision and apply **only to later recorded intervals**. Today's and this month's amounts may cover only part of those periods. The dashboard shows **energy coverage** and **tariff-priced coverage** separately.

The detailed cost page shows import kWh and expense broken down by named category and entered rate, export kWh / credit by FiT category, prorated supply charge, tax adjustments and the net result. Costs persist through Home Assistant restarts, but unrecorded history is **not backfilled**.

### Savings and value estimates

The separate, labelled **self-supply and export value** estimates what combined solar and battery self-supply might be worth under the active import and export rate at each interval. It is a comparison, not a measured net bill saving. The **battery discharge potential** is separate and overlaps those estimates; **do not add the two together**. Export-origin uncertainty, battery charging losses and grid charging can significantly change actual battery savings.

## Before relying on this

1. Verify the inverter's **grid polarity** against the actual utility meter during a known sustained import and export. It has not yet been independently field-verified for every SAJ inverter.
2. Compare daily meter kWh against the Home Assistant recorded intervals. This is a **power-integrated estimate**, not an energy retailer billing meter.
3. Configure exact tariff periods, weekends, tax treatment and signed export rates from your retailer contract.
4. Remember **AEMO live/wholesale prices are not connected**. This is a user-entered, static time-of-use model; wholesale AEMO numbers are not necessarily the rates on a retail electricity contract.

For Home Assistant's built-in Energy dashboard sensor selection, see [ENERGY_AND_COSTS.md](ENERGY_AND_COSTS.md). For installation and upgrade, see [INSTALLATION.md](INSTALLATION.md).
