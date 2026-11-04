# SAJ H2-10K-S3-A — export limitation and curtailment research (read-only)

Date captured: 2026-11-03 17:36:19 Australia/Adelaide (user-operated direct Modbus TCP). Inverter in Self-consumption mode. **All data are holding-register READS ONLY; no writes are authorized or performed.**

## Observed raw values

| Hex register | Raw | Field (candidate) |
| --- | ---: | --- |
| 0x364D | 1100 | Battery charge power limit |
| 0x364E | 1100 | Battery discharge power limit |
| 0x364F | 1100 | Grid charge / input limit |
| 0x3650 | 1100 | Grid discharge / inverter output limit |
| 0x365A | 1100 | Anti-reflux export power setpoint |
| 0x365B | 0 | Anti-reflux current setpoint |
| 0x365C | 0 | Anti-reflux mode (community decoder: OFF) |
| 0x3647 | 0 | Self-consumption mode |
| 0x4029 | 100 | Battery charge SOC upper limit |
| 0x402A | 15 | Battery discharge SOC lower limit |
| 0x402B | 90 | Battery depth of discharge configuration |
| 0x402C | 90 | Battery reserve SOC configuration (verify app semantics) |
| 0x4004 | 2 | Inverter status code (not independently decoded) |
| 0x4010 | 551 | Inverter temperature, likely 55.1 C |
| 0x4011 | 431 | Ambient temperature, likely 43.1 C |
| 0x406E | 290 | Battery temperature, likely 29.0 C |
| 0x406F | 10000 | Battery SOC 100.00%, independently verified mapping |

PV raw 0x4071..0x4079 = `[2779,943,2620,3224,243,794,3663,249,915]`.
Candidate PV groups: 277.9 V / 9.43 A / 2620 W; 322.4 V / 2.43 A / 794 W; 366.3 V / 2.49 A / 915 W.
Sum PV inputs = **4329 W**; reported aggregate at 0x40A5 = **4323 W**, an excellent agreement.

Raw power block 0x40A0..0x40AD = `[6994,0,0,0,0,4323,2671,6654,6999,6626,6996,0,49,0]`.
Community decode names: 0x40A0 total load power; 0x40A5 PV power; 0x40A6 battery power; 0x40A7 total grid power; 0x40A9 inverter power. **Do not declare 0x40A7 to be site export** or assume positive/negative signed direction before reconciling 0x4095-0x4098 direction flags, the per-phase meter/grid data, independent site meter and elekeeper. Note 4323+2671=6994 exact, requiring careful independent interpretation of 0x40A0.

## External reference mapping and open questions

- Community source `stanus74/home-assistant-saj-h2-modbus`, `custom_components/saj_h2_modbus/modbus_readers.py` decodes 0x365C values: 0 = "Not open anti-reflux", 1 = "Total power mode", 2 = "Phase current mode", 3 = "Phase power mode". Local anti-reflux therefore **appears disabled**, but local Modbus is not the only possible network export control.
- 0x364D..0x3650 raw power limit scaling is 0-1100 with 1000=100% and 1100=110% / default; these are **not watts**. 0x365A=1100 by itself does not establish any permitted export limit while 0x365C=0.
- Exact homeowner's SA Power Networks fixed vs Flexible Exports connection agreement is unknown. Dynamic commands, separate gateway/CT device, firmware grid compliance functions or other settings may impose tighter limits.
- The SAJ H2-S3 manual differentiates grid export limitation from inverter generation limiting. **Do not equate a grid-export setting to MPPT/DC solar curtailment.** No manufacturer-verified Modbus register for standalone PV curtailment has been established.
- Battery SOC was full and PV was generating about 4.3 kW late afternoon, but this observation does not show curtailed available sunlight or an active negative-FiT export policy.
- Verify battery reserve values 0x402B/0x402C against elekeeper before using as safety thresholds. Do not write any SOC/protection/BMS register.

References:
- SAJ H2-(5K-10K)-S3 Australia manual, section 6.7: `https://au-img.saj-electric.com/file/30302834_H2-%285K-10K%29-S3%20User%20Manual_en_AU_V2.1-20240314052916177.pdf`
- Community register map: `https://github.com/stanus74/home-assistant-saj-h2-modbus/blob/main/register_overview.md`
- Community decoder (anti-reflux enum): `https://github.com/stanus74/home-assistant-saj-h2-modbus/blob/main/custom_components/saj_h2_modbus/modbus_readers.py`
- SA Power Networks Flexible Exports: `https://www.sapowernetworks.com.au/your-power/your-solar/`

## Second diagnostic — midday grid export (2026-11-04 14:04:38 Australia/Adelaide)

User executed the second requested **read-only** Modbus test in the Home Assistant container. The terminal paste was partly garbled, but output completed; no write functions were in the script and the complete requested blocks were printed.

### Raw capture

- Export control: `0x365A=1100, 0x365B=0, 0x365C=0`, unchanged from 2026-11-03.
- Inverter-side phase/grid block `0x4031..0x4044`: `[2487,2648,5001,65530,5877,6588,891,0,0,0,0,0,0,0,0,0,0,0,0,0]`. Mapped as R-grid 248.7 V, 26.48 A, 50.01 Hz, 5877 W inverter-side grid port real power; S and T phase fields zero. `0x4034=65530` is -6 signed; the earlier quick test only printed signed for three fields.
- Direction flags `0x4095..0x4098=[1,1,1,1]`; semantics not independently verified; do not interpret blindly.
- Realtime `0x40A0..0x40AD=[943,0,0,0,0,6277,13,5848,6599,5821,6602,0,53,60189]`.
  - `0x40A0=943 W`: site load/house consumption (community mapping).
  - `0x40A5=6277 W`: PV total.
  - `0x40A6=13 W`: battery essentially idle; verify sign with live app before relying on small readings.
  - `0x40A7=5848 W`: inverter-side total grid output; **not the metered site import/export**.
  - `0x40A9=5821 W`: inverter output.
  - `0x40AD=60189` interpreted as signed int16 **-5347 W**, strong evidence of **net site export**. Community SAJ decoder labels this `gridPower`; another SAJ H2 template labels it `SysGridPowerWall` and uses signed positive-import/negative-export.
  - Energy check: `6277 - 943 - 13 = 5321 W`, within 26 W of -5347 W signed site export. Variation likely asynchronous register samples or sensor tolerances; this is compelling but not yet physical meter proof.

### Interpretation and follow-up

- This snapshot proves there is substantial measured solar output and likely **~5.35 kW site export** with little battery charge/discharge at that time. It does **not** prove network export permission, curtailment, or absence of dynamic limits.
- `0x4035` (inverter/grid port) and `0x40A7` (inverter grid power) are about 5.8 kW positive; they do **not** match the site balance and must **not** be used to compute site revenue or export control feedback. This differentiation is important for grid power sign handling in Home Assistant.
- Community SAJ register list: `https://github.com/stanus74/home-assistant-saj-h2-modbus/blob/main/register_overview.md`
- Independent per-phase metering investigation (Oct 2026): `https://github.com/evcc-io/evcc/issues/34757` reports actual meter phase power at `0xA03F,0xA045,0xA04B` signed positive import/negative export, distinct from inverter-side `0x4035` power. This is **external user evidence** on a different SAJ H2 and needs owner-specific readback validation.
- SAJ manufacturer configuration guide, page 41 (total export cap vs phase caps) and page 67 (Export/Generation Limitation Settings, optional hard vs soft): `https://au.saj-electric.com/hubfs/Guides%20and%20Manuals/HS3/H2_HS2_HS3_AS2_AS3_Configuration_Instructions_V1.0_en.pdf`.
- **Next safe step**: read only `0xA03D` count 18 (three phase meter A values) and contemporaneous `0x40AD`; compare meter sum of signed phase real powers, grid power and elekeeper. Never infer safe curtailment controls from negative FiT or local anti-reflux mode alone.

## Third diagnostic — Meter A agrees exactly with system net grid power (2026-11-04 14:09:38 Australia/Adelaide)

The homeowner ran another strictly read-only diagnostic of holding-register blocks `0xA03D` count 18 and `0x40AD` count 1. Terminal input had an inconsequential garbled paste fragment, but the complete read program ran and reported no setting changes.

### Verified raw capture

```
0xA03D = 2489    # Meter A phase 1 voltage: 248.9 V
0xA03E = 3275    # Phase 1 current: 32.75 A
0xA03F = 57864   # Signed int16 = -7672 W net phase 1 power
0xA040 = 8146    # Meter A phase 1 apparent power: 8146 VA
0xA041 = 64595   # Signed int16 = -941, candidate PF = -0.941
0xA042 = 5004    # Meter A phase 1 frequency: 50.04 Hz
0xA043..0xA04E = all 0   # Phase 2 and phase 3 fields unavailable/zero
0x40AD = 57864   # Signed int16 = -7672 W system net grid
```

- **Meter phase sum = -7672 W; system grid power 0x40AD = -7672 W; mismatch = 0 W.** This independently corroborates that `0x40AD` is the correct signed **net site grid-exchange** signal for monitoring on this SAJ H2 installation (negative export; positive import). It is *not* independently verified against a utility revenue meter.
- Internal consistency: `248.9 V × 32.75 A ≈ 8151 VA` versus measured `8146 VA`; `7672 / 8146 ≈ 0.942` versus signed power-factor raw `-941` / 1000. Inverter appears to have **one active metered phase**, with phase 2/3 zero; verify meter topology before asserting service connection phase configuration.
- Snapshot demonstrates **approximately 7.672 kW real power export** at this instant. It is greater than 5 kW, but **does not establish a compliance violation or a granted export allowance**; SAPN flexible exports, site connection agreement, additional export controller and momentary dynamic operating envelope remain unknown.
- Since this reading occurred five minutes after the earlier 14:04 PV balance, do NOT combine the two snapshots to derive a simultaneous PV/load balance.
- **Control design consequence:** monitor signed `0x40AD` as net export/import; do not substitute `0x4035` or `0x40A7` inverter-side output signals for export-limiting feedback. More importantly, do not implement a write to an unverified anti-reflux/generation-limit register. PV curtailment remains research-only; only user-confirmed hardware/firmware control semantics and a safe recoverable commissioning plan could permit changes.
- Follow-up with owner: inspect (without touching Save) the elekeeper **Export/Generation Limitation Settings** screens and establish SAPN fixed/Flexible Exports approval and any dynamic export gateway. A screenshot of those settings would materially help map the live configuration.

## Owner-observed day versus night export ceiling — hypothesis, NOT authorized limit (2026-11-04)

The owner reports a **roughly 10 kW export ceiling in daylight and apparently ~1.5 kW grid export at night**, despite expecting more nighttime battery export. On 2026-11-04 the owner **clarified option B**: they have **actually tried discharging the battery at night**, and observed **net grid export plateauing at approximately 1.5 kW despite the battery being capable of greater output**. This is an observed physical behavior, **not** a claim that elekeeper displays a configured 1,500 W limit. It is **not yet** a simultaneous nighttime Modbus trace or documentary confirmation of an approved export connection. It aligns with the owner's direct midday net-export measurement `0xA03F=0x40AD=-7672 W`, proving that at least one daytime instantaneous export exceeded 1.5 kW.

**Public policy facts (verified, distinguish from hypothesis):**
- SA Power Networks says Flexible Exports varies site export limits between ~1.5 kW and up to 10 kW per phase in standard areas, dependent on network conditions, system capacity and communications. See `https://www.sapowernetworks.com.au/industry/flexible-exports/`.
- SA Department for Energy and Mining confirms that CSIP-AUS/IEEE 2030.5 implements a 1.5 kW automatic **communications-loss fallback** if valid limit updates are not restored within a reasonable time; no evidence yet that this homeowner's communications failed: `https://www.energymining.sa.gov.au/industry/hydrogen-and-renewable-energy/solar-batteries-and-smarter-homes/regulatory-changes-for-smarter-homes/dynamic-export-limits-requirement/questions-and-answers-for-industry`.
- SAPN states that solar in a hybrid PV/battery system must be dynamic-export capable, while the storage system is exempt from those *technical dynamic capability requirements*. **Not** proof of permission to export arbitrary battery power at night or override whole-site limits.
- SAPN historical Flexible Exports trial material describes a high variable limit communicated **during daylight hours**; this might explain an apparent day/night difference, but does not establish the contractual or technical behavior of the owner's installation: `https://www.sapowernetworks.com.au/public/download.jsp?id=320975`.

**Competing explanations to distinguish (no assumed root cause):** (a) nighttime scheduled dynamic operating envelope/expiry returning to fallback; (b) CSIP-AUS communications or heartbeat loss/timeouts, perhaps coincidentally appearing at night; (c) separate installer/gateway nighttime export configuration; (d) inverter firmware battery-export constraint or VPP setting; (e) measured battery discharge/available power and house load rather than a site-export cap.

**Safe next evidence:** Ask owner whether the 1.5 kW is displayed *as an export limit* in elekeeper, or an observed plateau of **actual net grid export** while battery output is higher. Request simultaneous nighttime screenshots of elekeeper battery power, home consumption, solar power and grid export, optionally read-only `0x40AD`, `0x40A5`, `0x40A6`, mode `0x3647`, export-control `0x365A..0x365C`. Do **not** command discharge just for this test. If available, inspect dynamic-export gateway health, received operating envelope/time stamp and commissioning paperwork. Avoid local Modbus register writes or limits changes; network-authorized export envelopes take precedence.

**Design impact:** Treat `10 kW by day / 1.5 kW at night` as a *user-observed pattern*, never a confirmed device setting or automatically enforceable/reprogrammable export schedule. Future VPP dispatch cannot assume nighttime high-rate battery export, must have verified effective time-varying site limit and fail closed when this is missing. Keep curtailment and live VPP commands disabled.

## Elekeeper screenshot verification — 2026-11-04 afternoon (read-only visual evidence)

Owner supplied screenshots of the local inverter elekeeper configuration pages. **Avoid publishing the pictured inverter serial number in logs/docs or screenshots.**

1. **Export limitation setting** screen shows `All Day Export Limitation Settings: Off` and a separate clickable **`Time of Use Export Limitation Settings`** menu. The Off status matches read-only Modbus `0x365C = 0` (community decoder: anti-reflux disabled). Do **not** infer that TOU export limits are disabled: its submenu settings have not yet been shown. Do **not** infer that SAPN dynamic limits are disabled either.
2. **Max Grid Input Current Limit** screen shows `Off`. This controls input not export, and cannot explain or prove any night export cap on its own.
3. **Safety Settings** shows Country Australia and code `AS4777_AustraliaA`. UI timezone option says `(UTC+09:30) Adelaide` while the phone screenshot is from November (Adelaide summer daylight-saving is UTC+10:30). App screen shows inverter time `2026-11-04 14:17:42`, while phone status-bar clock is ~`14:48` on the same displayed screenshot. This **may** indicate stale app data, bad clock sync, or a time offset; it **does not establish** either. Accurate device local time and DST handling are prerequisites for relying on TOU export limit window configuration. Recommend read-only refresh/observation before considering use of `Auto time sync`; do not change clock/timezone without confirming effect on all active TOU schedules.
4. **Feature Parameters** screenshot shows grid function words and inverter expansion options, neutral-to-ground detection `enabled`, Grid compliance curve selected (truncated), Maximum DCI `1000 mA`, Maximum Earth Leakage Current `200 mA`. These are **protection/compliance settings**: no project writes and no requested changes. No screenshot evidence of actual PV curtailment.

Official SAJ H2/HS2/HS3 Configuration Instructions, Export/Generation Limitation Settings page 67: https://sp.saj-electric.com/hubfs/Guides%20and%20Manuals/HS3/H2_HS2_HS3_AS2_AS3_Configuration_Instructions_V1.0_en.pdf. Manual identifies a separate time-of-use export limitation menu. Another SAJ model family manual explicitly describes time-of-use export limitation as daily time-window limits: https://ro.saj-electric.com/hubfs/Guides%20and%20Manuals/H2/H2-%285K-12K%29-LS2/en/H2-%285K-12K%29-LS2_User_Manual_en.pdf. **Model-specific behavior still to be verified on this device.**

SA Power Networks confirms a variable Flexible Exports limit up to 10 kW/phase with lower fallback at 1.5 kW in standard areas (or 0 kW for specified lower-hosting-capacity/SWER sites); communications failures can trigger the fallback. Source: https://www.sapowernetworks.com.au/industry/flexible-exports/ and government technical FAQ https://energymining.sa.gov.au/industry/hydrogen-and-renewable-energy/solar-batteries-and-smarter-homes/regulatory-changes-for-smarter-homes/dynamic-export-limits-requirement/questions-and-answers-for-industry. This is still **a possible cause of owner's nighttime observation, not proof**.

**Next single request:** User taps **Time of Use Export Limitation Settings** and sends an image of all settings displayed, with no changes or Save. Check whether any nighttime 1500 W window exists. If not, investigate dynamic-export gateway/CSIP operating envelope, comms fallback, and whether observed 1.5 kW is a measured plateau rather than an applied limit. Under no circumstances bypass grid/export limits or disable compliance functions.

## Next read-only field work

1. Re-read 0x365A-0x365C and identify the corresponding elekeeper "Export Limitation Settings" page, **without saving**.
2. Capture 0x4095-0x4098 direction flags, 0x4031..0x4044 phase grid measurements, and 0x40A0..0x40AD power together, with exact timestamps; compare against the live elekeeper flow and/or independent electricity meter.
3. Independently establish whether any SAPN dynamic site-wide export limit applies and how the device receives it.
4. Capture comparable midday data with high sunlight, battery near 100%, known load and grid export. Only then assess possible solar clipping/curtailment.
5. Preserve unchanged everything else (mode, TOU registers, charge/discharge percentages, BMS limits, export settings). No control write experiments or automatic restoration without explicit owner permission and manufacturer-level assurance.
