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

## Next read-only field work

1. Re-read 0x365A-0x365C and identify the corresponding elekeeper "Export Limitation Settings" page, **without saving**.
2. Capture 0x4095-0x4098 direction flags, 0x4031..0x4044 phase grid measurements, and 0x40A0..0x40AD power together, with exact timestamps; compare against the live elekeeper flow and/or independent electricity meter.
3. Independently establish whether any SAPN dynamic site-wide export limit applies and how the device receives it.
4. Capture comparable midday data with high sunlight, battery near 100%, known load and grid export. Only then assess possible solar clipping/curtailment.
5. Preserve unchanged everything else (mode, TOU registers, charge/discharge percentages, BMS limits, export settings). No control write experiments or automatic restoration without explicit owner permission and manufacturer-level assurance.
