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

## Next read-only field work

1. Re-read 0x365A-0x365C and identify the corresponding elekeeper "Export Limitation Settings" page, **without saving**.
2. Capture 0x4095-0x4098 direction flags, 0x4031..0x4044 phase grid measurements, and 0x40A0..0x40AD power together, with exact timestamps; compare against the live elekeeper flow and/or independent electricity meter.
3. Independently establish whether any SAPN dynamic site-wide export limit applies and how the device receives it.
4. Capture comparable midday data with high sunlight, battery near 100%, known load and grid export. Only then assess possible solar clipping/curtailment.
5. Preserve unchanged everything else (mode, TOU registers, charge/discharge percentages, BMS limits, export settings). No control write experiments or automatic restoration without explicit owner permission and manufacturer-level assurance.
