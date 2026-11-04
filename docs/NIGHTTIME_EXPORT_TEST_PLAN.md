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

## Field result: confirmed nighttime export plateau during supervised TOU discharge (2026-11-04 22:27–22:29 +10:30)

The owner used the existing Home Assistant SAJ H2 schedule editor to **save** a Wednesday 22:23–22:35 recurring discharge slot at **30% (~2,970 W estimated maximum)** and switched to **Time-of-Use mode 1**, verified by Home Assistant's live Modbus readback. Their live UI screenshot at approximately 22:26 shows ~503 W home, 2.02 kW actual battery discharge and 1.50 kW export (SOC 95%, PV 0 W).

The owner then ran six read-only observations through \`scripts/read_only_export_trace.py\`:

| Local time | Home W | Battery W actual | Site export W | Independent meter export W |
| --- | ---: | ---: | ---: | ---: |
| 22:27:03 | 509 | 2013 | 1504 | 1484 |
| 22:27:24 | 515 | 2024 | 1509 | 1489 |
| 22:27:44 | 514 | 1970 | 1456 | 1437 |
| 22:28:05 | 513 | 1986 | 1473 | 1473 |
| 22:28:26 | 511 | 2043 | 1532 | 1533 |
| 22:28:46 | 500 | 1956 | 1456 | 1456 |

- **Arithmetic means:** battery **1998.7 W**, house **510.3 W**, site export **1488.3 W**. Physical energy balance matches sample by sample: \`battery - house = site export\`, because PV=0.
- Actual export range **1456–1532 W**, all within 44 W of a ~1500 W target, despite a **~2970 W requested discharge ceiling** and household demand ~500 W; if unconstrained and fully dispatched, export capacity would have been ~2470 W. This is **strong evidence** of an **enforced effective net-site export cap near 1.5 kW at night**. It corroborates the owner's earlier lived experience; **not yet proof of what system or institution imposed the cap** (network operating envelope vs communications fallback vs gateway/firmware configuration).
- Meter A independently agrees within ~0–20 W during most export readings, as expected with sequential reads.
- Each sample reported **mode 1**, **anti-reflux mode raw 0**, **SOC 95.00%**, **battery temperature 21.0 C**, PV zero, and zero block read errors.
- **Safety/cleanup essential:** The Wednesday discharge schedule **repeats weekly**. User was instructed to switch back to verified Self-consumption, delete and **save** the discharge schedule, and re-read to confirm **0/7 charge, 0/7 discharge, mode 0**. The user **has not yet supplied verification of cleanup**. Do not treat the test as completed operationally until the post-test device readback confirms these final conditions; never rely solely on its ending at 22:35.
- **No further forced-discharge tests** are needed to establish the plateau. Investigate effective SAPN export-limit communication, approval, gateway and logged operating envelope via read-only channels. Don't write to unverified export-limit or voltage regulation registers.


## Root-cause source attribution protocol — follow-up to 2026-11-04 field test

**Important new comparative evidence (public, not proof for our site):** Other SA flexible export owners reported automatic reductions to 1.5 kW around **20:45–20:47**, including a FoxESS user who believed their dynamic commands stopped around **20:30**, with a roughly 15-minute instruction timeout. The exact expiry mechanism and cause were not independently verified. See the dated January 2026 Whirlpool posts:
\`https://forums.whirlpool.net.au/thread/9vw4yv4x?p=-1\`.
**Never suggest defeating these restrictions**; network instructions and default limit are connection safety constraints.

**Best discriminator: the *site-specific* exported allowance recorded by SAPN at this exact interval**. Community members report that \`https://portal.sapowernetworks.com.au/\` sometimes provides a graph labeled **Export Limit** after choosing **Access to data from a property**. This is a community-reported portal workflow, NOT an officially guaranteed user entitlement; options may vary with account permissions. Check **2026-11-04 20:00–23:00 Australia/Adelaide**, especially **22:27–22:29**, and if available compare daytime when 7.672 kW was physically exported. Do not substitute the public postcode/area *Service Performance Checker* for the exact site's command history. Redact address, NMI, account and identifiers in screenshots.

### Direct read-only SAJ control-source fingerprint

At the Kamrui SSH prompt, after any active test has been restored safely, run:

\`\`\`bash
curl -fsSL https://raw.githubusercontent.com/userdc-dev/saj-h2-control-enhanced/vpp-preview-overnight-guard-20261103/scripts/read_only_export_source_probe.py | docker exec -i homeassistant python -
\`\`\`

This executes ONLY known Modbus FC03 reads: 0x3606..07 saved **charge/discharge masks**, 0x3647 mode, 0x364F..50 grid-port input/output percent, 0x365A..5C local anti-reflux/limit, 0x4031...36 grid voltage/frequency/inverter grid-port output, 0x406D..6F battery temperature and SOC, 0x40A0..AD house/battery/solar/site-grid, 0xA03D..42 independent meter phase-1. It **does not read SAPN's communications heartbeat or the active CSIP-AUS envelope**—register addresses for those are unknown on this firmware, and we won't invent them. The purpose is to verify *whether local controls themselves changed* and verify no weekly schedule remains active.

### Attribution matrix

| Site-specific SAPN limit | SAJ behavior / CSIP-AUS status | Diagnosis |
| --- | --- | --- |
| SAPN **issued 1.5 kW** specifically at 22:27 | SAJ exports ~1.5 kW | Genuine authorized network-set envelope (unless later evidence shows contradictory site status). |
| SAPN **issued >1.5 kW** at 22:27 | SAJ locally holding ~1.5 kW; CSIP heartbeat expired / lost client connectivity / old command age | **Fallback path** likely; determine whether failure is the SAPN server, SAJ client, internet/dongle, or proxy aggregator using vendor/SAPN logs. Do not assume general internet connectivity proves CSIP client health. |
| SAPN **issued >1.5 kW** at 22:27 | Client reports recent valid receipt / correct downstream limit but SAJ remains ~1.5 kW | SAJ firmware/site controller/installer setting path more likely; seek vendor per-device effective limit and command arbitration audit. |
| SAPN history **unavailable**, or only area-level checker | SAJ exports ~1.5 kW | Root cause **still cannot be assigned**. Report precisely that the plateau is established, source isn't. |

SAPN official: \`https://www.sapowernetworks.com.au/industry/flexible-exports/\`. South Australian Energy & Mining FAQ: \`https://energymining.sa.gov.au/industry/hydrogen-and-renewable-energy/solar-batteries-and-smarter-homes/regulatory-changes-for-smarter-homes/dynamic-export-limits-requirement/questions-and-answers-for-industry\`.

The case should request SAPN and/or SAJ/installer:
- Confirm connection approval: *fixed vs flexible*, commissioned status and relevant-agent/communications-provider type.
- Identify manufacturer/model of CSIP-AUS **software client** (native inverter, separate gateway, or cloud proxy) and manufacturer of the export-limiting meter/CT.
- For **2026-11-04 20:00–23:00 Adelaide local**: actual utility-server export allowance time series, command issue times, command validity/expiry, **last successfully received/acknowledged instruction**, site communications state and any fallback event.
- If SAPN reports healthy >1.5 kW during the 22:27 test, SAJ should provide *actual effective site export limit at 22:27*, the origin of the prevailing instruction, any fallback mode and logs explaining why it took priority over the unsaved/off local export UI controls.
- Do not request changes to inverter protection or limits for diagnosis.

### Status gating

The owner has **not yet confirmed restoration of the Wednesday recurring 22:23–22:35 discharge slot** after the live test. Before any further commands that *write* to the inverter, explicitly verify mode=0 and discharge mask=0 (0x3607); returning Self-consumption alone does not clear this weekly slot. Reading status is safe. A failure in schedule cleanup needs manual inspection; no automatic blind retries.
