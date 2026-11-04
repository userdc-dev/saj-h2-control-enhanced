# SAJ H2: investigation of observed ~1.5 kW night export plateau

Status: **PLANNING AND READ-ONLY MONITORING ONLY**. Not authorization for inverter writes or battery dispatch.

## Confirmed owner facts (4 November 2026, Australia/Adelaide)

- SAJ H2/H2-S3 hybrid, ~10 kW inverter, SAJ B2 40.96 kWh battery, 3 PV arrays.
- On 2026-11-04 14:09:38+10:30 inverter-accessible meter-A phase-1 power `0xA03F` and system net grid `0x40AD` both read **-7672 W** (net site export). Other meter phases read zero. Daytime output **did exceed 1.5 kW**; not proof of an approved fixed daytime maximum.
- Owner reports up to ~10 kW export during daylight, but **when requesting TOU discharge at night, export appeared capped near 1.5 kW, usually from around 20:30–21:00 local time**. The battery is capable of a higher discharge.
- User's all-day and TOU local export limitation screens were both **Off**; temporarily selecting **On** merely displayed underlying fields, **Save was not pressed**. Anti-reflux `0x365C=0` observed.
- An *upper discharge setting* of 3 or 4 kW is sufficient to see an assumed 1.5 kW grid-export ceiling **only if house demand is low enough**. A battery may increase discharge rapidly when the house load rises, without increasing net export.
- Seven SAJ TOU charge/discharge slots can **repeat weekly**; reverting the operating mode is **not** a substitute for verifying stored schedules have been cleared or restored.

## Distinguish these hypotheses

1. SA Power Networks **current authorized dynamic site export allowance** is truly 1.5 kW at the observed time; inverter correctly follows the envelope.
2. The flexible-export communications client or gateway **falls back to 1.5 kW** when valid data or connectivity is lost.
3. A hidden SAJ/gateway/installer configuration caps export or battery discharge at certain times, independent of the two locally disabled UI controls.
4. Battery/SOC/power conditions, instantaneous consumption or voltage-based power derating limit observed output, masquerading as an export cap.

SAPN: `https://www.sapowernetworks.com.au/industry/flexible-exports/` and service performance/communications `https://www.sapowernetworks.com.au/your-power/your-solar/flexible-exports-service-performance-checker/`. The **site connection agreement and actual dynamic envelope prevail** over all user guesses and the inverter UI. SAPN documents a 1.5 kW communication-loss fallback for ordinary sites; this is **not confirmation that the owner's particular system has failed**. Battery storage's technical exemption from dynamic-export equipment compliance **does not provide permission to breach the approved site-wide grid export limit**.

## Phase A — immediate, harmless measurement verification

At the Kamrui host SSH prompt (`ssh kamrui@172.16.1.15`) with the current Home Assistant Docker container running, run once:

```bash
curl -fsSL https://raw.githubusercontent.com/userdc-dev/saj-h2-control-enhanced/vpp-preview-overnight-guard-20261103/scripts/read_only_export_trace.py | docker exec -i homeassistant python - --host 172.16.1.4 --samples 6 --interval 20
```

Observe: timestamp, PV, house W, battery aggregate W, SOC, battery temp, signed site net grid and independent meter total. Read failures are marked and may need checking. Negative grid = export, positive grid = import. Readings from multiple blocks are sequential, not perfectly simultaneous, so rapid house load spikes cause transient mismatches. **No writes or mode changes; no necessity to set TOU.**

Return the complete output. We can correct decoding/units before relying on the logger.

## Phase B — simple baseline around expected transition

If Phase A passes, use the same read-only command once around 20:15–20:25 and again around 20:50–21:10 Adelaide local time (or at other times the owner actually observes the restriction). This may reveal changes to site meter and local register values, **but in Self Consumption without export demand, no low-export observation proves a 1.5 kW ceiling**.

Optional: screenshots of elekeeper current status (PV, house, battery, grid) from the same time. Use times noted by the phone; the Docker container timestamps may be UTC rather than Adelaide. Do not introduce new discharge commands solely to capture read-only data.

Separately obtain the installation/commissioning **SAPN Small Embedded Generation (SEG) approval** stating fixed/flexible choice; if using Flexible Exports, identify actual inverter/gateway CSIP-AUS connection status and permitted operating envelope at 20:15 and ~21:00. The public area performance checker is **not proof of the site's instantaneous limit**. Owner should redact name, address, NMI, account numbers before sharing documents.

## Phase C — only after permissions and safeguards confirmed

**Not approved yet.** A technician-supervised controlled test can use **3 kW or 4 kW requested discharge limit**, not the 10 kW maximum. No solar production preferred. To distinguish a ~1.5 kW plateau, use periods when home demand is under `requested discharge - 1.5 kW` (subject to losses). For a 3 kW request, best demand below ~1.5 kW; for 4 kW below ~2.5 kW.

Before ANY live TOU write:
- Verify **site-wide export agreement, contemporaneous dynamic allowance, and how inverter enforces it**. A 3–4 kW discharge request can temporarily export up to around 2–3.5 kW when house load is low and no cap is active. Never assume the 1.5 kW cap exists for safety.
- Verify battery state, SOC safety margins, temperature, alerts, current mode, and all 7 existing weekly charge/discharge slots by readback and saved backups.
- Provide an **independent fail-safe stop/recovery path**, with a human present, beyond an HA timer. HA process crash, Ethernet loss, or power loss must not leave unintended recurring slots. No Off-grid or Backup mode.
- Verify whether firmware can restore a *one-shot* test safely. Current quick actions are dry-run-only and cannot guarantee rollback of weekly schedules, so **do not use them to command a physical timed discharge**.
- If authorized later, log every ~10 seconds during a short run and monitor `export W`, `house W`, `battery actual W`, `SOC`, voltage and alarms. Stop on unexpected export, import behavior, heat/alarms, loss of telemetry, site-limit uncertainty or inability to recover. Capture verified restore and final state before declaring completion.

Steady-state example under *hypothetical* 1.5 kW site cap, no PV and 4 kW discharge setting:

| House W | Battery actual W | Site export W |
| ---: | ---: | ---: |
| 500 | 2000 | 1500 |
| 1500 | 3000 | 1500 |
| 2500 | 4000 | 1500 |
| 3500 | 4000 | 500 |
| 4500 | 4000 | -500 (import) |

These are idealized and cannot be assumed to occur. Especially at load spikes, battery response and export metering will lag. Derive **actual net export** from independently verified signed `0x40AD`, not from discharge-command targets, inverter grid-port `0x4035`, or `0x40A7`.

## What user should provide first

1. **Phase A output** (read-only, no forced discharge).
2. If available, the redacted **SAPN connection/export approval** or installer's statement confirming Flexible versus fixed export and dynamic gateway type.
3. A screenshot from the elekeeper live status page at the time the night cap is observed naturally; note mode and whether any old TOU schedule was active.
4. Only if Phases A/B and safeguards pass, agree separately on exact supervised discharge test setup.

## GitHub safety checks

CI `.github/workflows/safety-tests.yml` exercises `tests/test_export_readonly_trace.py` with an offline fake Modbus client and the owner's known meter values. This verifies decoding and failure handling without contacting an inverter. It is **not** physical commissioning approval or evidence that the 1.5 kW export ceiling is due to SAPN.
