# Solar forecast: historical learning and real accuracy (v0.5.19)

**Built into this repository.** No YAML, no extra GitHub integration and no inverter writes. The editable SAJ H2 Control forecast still uses Open-Meteo for expected solar production, your panel groups and orientations, efficiency and the existing live power/charging data. This update extends that model with **older Home Assistant long-term statistics**, seasonal corrections, a conservative backtest and forward accuracy tracking.

## What the new learning can and cannot do

### 1. Examine past recorded solar output

Under **SAJ H2 Control → Solar forecast → Forecast learning & accuracy**, choose **30 days, 90 days, 6 months or 12 months** and click **Analyse past readings**.

It uses Home Assistant's **hourly long-term statistics** from existing read-only SAJ PV power and battery SOC sensors, not raw or writable inverter registers. The source may be the old SAJ H2 Safe Monitor sensors or the more recent user-friendly power/SOC aliases. The code prefers the older sensor if it has enough usable statistics.

Home Assistant usually purges **detailed states after about 10 days**, while long-term hourly statistics can remain indefinitely **if the sensor had a valid state class, Recorder was enabled and statistics were actually retained**. The integration cannot recreate readings from before those entities began recording. Therefore selecting 6 or 12 months means the **lookback limit**, not a claim that many months are available.

For each potential historical hour, it:

- Reads the actual measured **hourly mean PV power (W)**, approximately converting to hourly kWh using W/1000; this is not a verified utility metering integral and can be biased by incomplete hours.
- Reads the same hour's **maximum battery SOC**; **missing SOC is excluded** because it cannot prove that production was not curtailed.
- Requests **historical weather reanalysis** (Open-Meteo archive, global tilted irradiance and cloud cover) for each configured panel azimuth/tilt group, using the configured Home Assistant latitude/longitude. That archive provides hindsight weather estimates—not actual weather forecasts issued months ago.
- Aligns each preceding-hour radiation value with the same *physical* Home Assistant hourly sample and uses its **midpoint in Home Assistant local time**, including South Australia's half-hour offset.
- Requires clear skies (cloud cover ≤25%), expected solar output ≥0.7 kWh/h, and battery SOC <97%; excludes very large mismatches that might indicate curtailment or bad readings. Weather and SOC guards reduce contamination but cannot eliminate all shade, inverter export limits or VPP effects.

### 2. Only deploy season/time-of-day corrections that pass a backtest

The model distinguishes **summer, autumn, winter and spring** using the property's latitude (Southern Hemisphere seasons apply automatically in Adelaide). Qualified historical hours are divided **chronologically** into the earlier ~70% used to learn, and the later ~30% **unseen holdout** used to check whether that learning worked. At least 20 training hours and 8 holdout hours are required. Hour-of-day bins require several matching samples; sparse bins fall back to the original forecast.

Corrections are bounded to **65%–115%** and dampened toward the original physical model. The historical calibration is **only deployed if its held-out mean absolute error (MAE) improves by at least 2%**, and otherwise it is held back. The model retains the existing cautious live clear-sky learning as a fallback and blends it with validated seasonal factors **without multiplying the two corrections**.

**Important:** This is a *retrospective weather-reanalysis model backtest*, not proof that the model would have predicted those past days ahead of time. It should be used to tune physical panel efficiency and seasonal/hourly patterns, not to claim improved weather forecasting accuracy.

A change to the physical panel layout/efficiency resets historical calibration and previously logged forecast accuracy, so corrections from a different installation are not silently reused.

### 3. Evaluate forecasts actually issued BEFORE the target day

From the upgrade onward, when a fresh weather forecast is obtained, the integration can store the **next day's** predicted PV production *before the target day begins*. It never reconstructs an old issued forecast from today's weather.

After that day completes and hourly power statistics exist, it scores **07:00–18:59 forecast kWh against 07:00–18:59 observed kWh**, using the **same time window** on both sides. A score is withheld for incomplete coverage: at least 9 of 12 daytime hourly readings are required, including morning and afternoon.

The dashboard shows:

- **Forward MAE (kWh)** and number of actual saved-beforehand daily predictions scored.
- Once there are **10 scored days**, MAE for the previous five compared to the latest five, with an **indicative trend** (improving, similar or worsening).
- The trend is descriptive only: weather differs day to day and ten observations cannot statistically establish a lasting improvement.

These are daytime energy estimates based on hourly mean power, not full-day certified metered energy. Complete-day generation and inaccurate weather may still differ.

### 4. Automatic and manual updates

- An initial bounded history scan starts after Home Assistant loads the control integration. It **does not block existing TOU controls** and a failure cannot force an inverter action.
- A periodic scan checks again around every 7 days while Home Assistant is running. It avoids re-fetching weather more than once per 7 days unless manually requested.
- The **Analyse past readings** button lets you retry when more statistics accumulate.
- Historical calibration factors, candidate/holdout results, scan status and newly issued forecast logs live in the integration's **existing Home Assistant storage**, surviving normal restarts.
- If Recorder history, SOC statistics or archived weather are absent, it reports that limitation and falls back to the existing Open-Meteo model and live-hour learning **without inventing missing history**.

### How to interpret the indicators

| Indicator | What it really means |
|---|---|
| **Live calibration – N h** | Eligible clear-sky hours observed while this feature ran |
| **Historical model – Validated** | Historical calibration beat baseline on later held-out reanalysis-based hours |
| **Historical model – N h available** | Hours actually eligible for comparison; **not** whole days/months |
| **Forward accuracy – X kWh MAE** | Error of saved prior-day forecasts on matching observed daytime hours |
| **Improving (indicative)** | Most recent 5 scored predictions have lower MAE than preceding 5; not guaranteed improvement |

Expand **Calibration checks & limitations** to see the number of PV/SOC statistics, seasonal hours and baseline-vs-calibrated holdout MAE.

## Safety and privacy

These features **read** HA long-term statistics and remote public Open-Meteo weather only. Open-Meteo receives your Home Assistant configured coordinates to estimate irradiance for the panel orientations; the integration does not upload power usage statistics to Open-Meteo. **No inverter Modbus writes, schedule modifications, automatic battery exports, billing tariff changes, or required YAML.**

The old Home Assistant Energy sensors, cost model, TOU controls, seven charge/discharge schedules, Historic Data graph and editable solar layout remain unchanged. This feature has offline regression tests but still needs testing with the actual owner's HA Recorder statistics, Open-Meteo archive response and browser.

**Troubleshooting:** If learning shows zero eligible hours, first confirm the read-only SAJ monitor has stored long-term solar-power and battery-SOC statistics for more than one day; check Home Assistant **Developer Tools → Statistics** and Recorder settings. It is normal for a freshly installed monitor to have little history. Wait for more recorded days, or choose a shorter lookback; do not fabricate dates or manually alter statistics.
