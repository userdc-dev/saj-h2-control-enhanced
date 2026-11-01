# SAJ app operating-mode and Time-of-Use UI — observed contract

**Observed:** 2026-11-01, screenshots shared by owner. **Source:** Owner's SAJ mobile app screenshots; preserve facts below without uploading personal screenshots or identifiers to the public repository.

**Scope:** Observation and specifications, NOT confirmation of Modbus register write format, timing guarantees or deployed controls.

## Verified visible elements

### Operating Modes screen (while Self-consumption selected)

- Separate **Off-grid load backup enabled** toggle appears; in screenshot its switch appears enabled. This is a DISTINCT feature from choosing Backup operating mode. **Do not touch or conflate it with mode 2**, and never change this toggle through the new control integration without separate explicit authorization and safety research.
- **Off-grid AC Coupling** option, shown **Off**, with independent Save. This is also a distinct device setting, **not part of our planned mode toggle**. Leave unchanged.
- **Current mode** dropdown with **Self-consumption mode**, independent Save button.
- App describes Self-consumption: PV first supplies loads; surplus charges battery; remaining PV exported to grid.

### Operating Modes screen (while Time-of-use selected)

- **Current mode** dropdown includes **Time-of-use Mode**, with Save.
- App describes TOU: charge/discharge according to tariffs, and discharge can send surplus **to grid**. This is a real behaviour with possible export-compliance and tariff consequences. Do not assume discharge always serves house only.
- **Charge Settings +** and **Discharge settings +**, each adding independent slots.
- User explored and reports **maximum 7 charge entries and maximum 7 discharge entries** in SAJ app (14 total possible). This cap is a user observation that should be implemented as the *UI limit*, but exact device-side slot count/register layout remains to be verified.
- Each demonstrated **Discharge Time N** entry includes start clock time, end clock time, **Discharge power N** in watts, and **Workday N** multiselect.
- Screen example: Discharge Time 1 = **22:00–22:40**, Discharge power 1 = **9900 W**, app displays admissible input range **[0–9900] W**, Workday 1 = **Wednesday**. This was a visible *form value/example*, not proof that the device can safely discharge at 9900 W under every condition, nor proof that the schedule was saved or presently active.
- Workday chooser shows **Select All**, then Monday, Tuesday, Wednesday, Thursday, Friday, Saturday, Sunday; multiple days can be selected for each schedule. No implication that one schedule == one weekday.
- Corresponding **Charge Settings** fields were not expanded in provided screenshots. They likely resemble discharge fields, but **do not assert an exact charge-side range, schema or max power** until observed.
- **Non-charge/discharge time period settings (in time-of-use mode)** offers at least **Self-consumption mode** and **Standby mode**, with a separate Save action. User prefers **Self-consumption as the default outside scheduled windows**, NOT Standby.
- The fallback above is a **behaviour within TOU mode during unscheduled periods**, not necessarily a command to switch the overall operating mode back to 0. Keep these settings conceptually distinct in API and UI.
- There are Save controls that may apply per panel/setting; the exact transactional order and atomicity are unknown.

## Owner-observed timing

- The owner reports that changes in mode/TOU settings sometimes take **up to approximately 5 minutes** to take full effect and appear to take effect around **clock minutes divisible by 5** (e.g. :00, :05, :10). This is observation, **not a confirmed guaranteed scheduler or register-protocol rule**.
- Mode readback and schedule readback may update at different times. During that interval, do **not** assert completion or re-send updates repeatedly.
- Design proposed statuses: `Observed`, `Draft changed`, `Submitted—awaiting readback`, `Applied—awaiting effective window`, `Verified active`, `Timed out / unresolved`, `External change detected`, `Offline/stale`.
- The **readback verification deadline** and retry/backoff must be conservative and explicitly reviewed. Treat ~5 minutes as **initial observed latency only**, not as permission to wait forever, fire multiple writes, or activate unsafe fallback actions.
- A schedule's *configuration* can be confirmed by reading device setting registers, but **effective operation** also requires live mode and battery direction/power readings; these may differ because SOC limits, clouds or third-party controls intervene.

## Most important requirement: device is source of truth

Home Assistant should **show exact settings actually stored on the inverter** rather than just what the user last submitted or what is cached in HA. This is mandatory because the SAJ mobile app is another writer.

Proposed architecture:
1. On startup, and periodically thereafter, READ mode (0x3647), all 7 charge and 7 discharge slots, weekday masks, power setpoints and the *TOU non-scheduled fallback*. **Registers for slots are NOT YET KNOWN/VERIFIED**. Do not fabricate them.
2. Normalize read settings into a canonical, typed `DeviceConfigSnapshot` with source poll timestamp, mode, fallback and all entry slots. Treat unused/empty slots distinctly from 0 W entries.
3. User edits an explicit `DraftConfig`; diff against the current device snapshot; require user review and confirmation.
4. Future approved writer applies only proven supported fields; read back the full config and wait for observed propagation. Display **pending** and never show draft as active.
5. Periodically reconcile device vs HA. If the SAJ app changes settings, HA should detect them, update displayed settings and flag any unsaved local draft/conflict. **Never silently overwrite a change made in the SAJ app.**
6. Do not silently merge potentially overlapping control windows or reassign slot numbers. Keep slot IDs stable so changes match the device.
7. Detect and surface: mode selection mismatch, fallback mismatch, power mismatch, start/end mismatch, weekday mask mismatch, slot added/removed externally.
8. If readback is unavailable, controls remain disabled and status shows `unverified`. The read-only monitor continues functioning independently.
9. Detect *controller ownership* and conflicts. Official SAJ app previously showed **Under third-party control**; which component owns settings is unverified.
10. Actual charging/discharging must be confirmed using the safe monitor's **signed battery power** (negative charge, positive discharge), battery SOC, and other validated BMS status where available. Current live telemetry is insufficient to prove that a requested action is safe. Device-side controls can yield different actual power.

## Proposed UI

- Header: `Mode  [Self-consumption | Time-of-use]` (only those 2 selectable; read-only for now).
- TOU editor (visible if current/draft TOU): **7 charge rows + 7 discharge rows maximum**, compact start–end time, power W/kW, Monday–Sunday multi-select, row enable/remove; show device-synced vs locally-edited badges.
- Default outside schedules: `Self-consumption` (never silently choose `Standby`).
- Quick actions: `Charge for X min`, `Discharge for X min`, `Cancel`. Must **not** overwrite or silently destroy recurring TOU schedules. How temporary actions coexist with SAJ's device scheduling must be researched before implementation.
- No Off-grid, Backup, AC coupling or off-grid backup controls in this new UI.
- Display `Last device sync`, `Pending apply`, `Confirmed device state`, `Effective state`, drift and error details. Modbus-safe timestamp/heartbeat needed.
- Show a 5-minute activation *expectation* as estimated until measured; no misleading hard promise.

## Open issues / validation gates before any writable action

1. Read-only inspection of *actual* installed full TOU slot data, weekday mask coding, and fallback register; prove parity with SAJ app.
2. Verify numeric limits for charge power (not pictured) and discharge power (9900 W displayed in app), and whether it represents AC side/battery DC side.
3. Verify whether start==end, midnight crossing, schedule collisions, per-day selections, 0 W and duplicate windows are allowed. Avoid assumptions.
4. Identify which status is currently *configured* and which is *effective*, particularly at 5-minute boundaries; find device-register readbacks.
5. Confirm when/how a quick charge or discharge is *safely stopped and restored* without writing forbidden mode 2/3.
6. Check interaction with grid export compliance, battery reserve and BMS charge/discharge permission.
7. Confirm SAJ app/cloud vs direct Modbus precedence and synchronization latency. Inconsistent cloud/mobile UI may reflect refresh delays as opposed to register disagreement.
8. Only after the owner approves particular read-only discovery and documented safe control method should hardware-write testing be considered.

## Safety non-negotiables

- Never command **Backup 2** or **Off-grid/Passive 3**.
- Never change **Off-grid load backup enabled** or **Off-grid AC Coupling** as a side effect.
- Never interpret *TOU standby fallback* as a command to enter off-grid/passive mode.
- Never assume **9900 W** is an unrestricted safe power setting.
- No unsupported register writes, no unverified automatic mode switch, and no claims of immediate effect after a save.

**Implementation status:** observed specification only; no TOU readback registers have yet been verified; separate control repository remains *non-writing*.

## Additional owner clarification — schedule counts, time and power (2026-11-01)

- **Zero is a perfectly valid count**: 0–7 **charge schedules** and independently 0–7 **discharge schedules**. There is NO minimum of one. No active schedule must be fabricated or automatically inserted just because Time-of-use mode is selected.
- All times use **24-hour `HH:MM`**, e.g. `00:00`, `09:05`, `22:40`. Never render AM/PM in SAJ schedule editors. Decode upstream packed hours/minutes only after checking valid 0–23 and 0–59 bounds.
- The app shows **0–9900 W** for the discharge example. Owner suspects increments **may be 100 W** (0, 100, 200 … 9900), **NOT yet confirmed**. Do not restrict UI to multiples of 100 W or reject other values until the SAJ app or readback demonstrates this.
- Upstream `modbus_readers.py` decodes the low byte of each packed schedule register as `power_percent` (0–100 expected in usual use), not watts. It is *plausible* that app watts = percent × 100 W for this 10 kW model (e.g. screenshot 9900 W ↔ raw 99). **This scaling is unverified on this inverter** and could depend on power configuration; never use it to issue writes before real readback parity checks.
- With zero schedules, enable masks are expected to be zero *if* the upstream mapping applies. An all-zero slot's start/end/power may be stale data; use enable masks rather than inventing active slots.

## First live read-only TOU snapshot — confirmed 2026-11-01

Owner ran **function 03 holding-register reads only**, while the inverter was in Self-consumption. Real raw results:

- 0x3604 count 23: `[0, 1, 5888, 5947, 2103, 0, 827, 6170, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]`
- 0x361B count 21: `[5632, 5672, 1124, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]`
- 0x3647: `[0]` = Self-consumption
- 0x365F: `[1]` = TOU unscheduled fallback Self-consumption

Decoding by upstream layout:
- Charge enable mask **0** (no active charge slots), discharge enable mask **1** (slot 1 selected). **Do not treat nonzero unused charge-slot words as active schedules**; first charge slot contains inactive data 23:00–23:59, combined raw 2103 = high-byte 8 and low-byte 55. A second inactive slot contains stale/nonzero data too.
- Discharge slot 1: 5632=0x1600 → **22:00**, 5672=0x1628 → **22:40**, 1124=0x0464 → high byte weekday mask **4** and low byte power raw **100**. Start/end/weekday match user's SAJ app screenshot (Wednesday).
- IMPORTANT POWER SCALING CONFLICT: screenshot indicated **9900 W** while raw low byte is **100**, not 99. The naive `raw × 100 W` model is **contradicted by this example**. Possibly UI remaps 100 to a capped 9900 W setting; must validate using a new *safe, future, non-active* schedule value through official app and then read again. Do not hardcode a conversion.
- Mode **0** and discharge-enable mask **1** may coexist: slot configured but not currently being applied, because global mode is Self-consumption. Enabled/configured ≠ currently executing.
- Snapshot is **read-only** and does not authorize any control commands. Real schedule may still be present in inverter memory even when global mode 0.

### Next low-risk experiment

Keep global mode Self-consumption; do not enable Time-of-use or schedule execution for a diagnostic. In official app, optionally change **only a future inactive discharge-slot power value** while keeping 22:00–22:40 Wednesday window, provided owner verifies this cannot activate unexpectedly. Allow app's observed propagation time (~5 min), then re-read the same four blocks and compare changed raw value. Prefer to first confirm current saved SAJ app screen, since app UI and register might be out of sync. If unsure, do no mutation and only inspect existing saved values.

## Additional eLEKeeper confirmation (2026-11-01, 17:13 screenshot)

User supplied a fresh screenshot showing Discharge Time 1 = **22:00–22:40, 9900 W, Wednesday**. This matches the previous Modbus-decoded time and weekday and confirms the application-reported watt value. In the last Modbus baseline, corresponding power low byte was **100**, so watt conversion remains **unverified**; do not assume 100 raw means 10,000 W. The screenshot's **Current mode dropdown reads Time-of-use Mode**, whereas the *earlier* Modbus mode was 0 (Self-consumption). The screenshot does not prove the selection was saved/effective, and the earlier mode reading may be stale. **Next step is re-read actual mode and enable masks before modifying schedule values or performing any time-of-use test.** No Modbus writes.

## New power-step observations and hypothesis (2026-11-01)

Owner confirmed the eLEKeeper discharge power selector:
- Top value **9900 W**, which matches upstream **raw low-byte 100** in the observed Wednesday discharge slot.
- Next available lower value **9800 W**; **9801–9899 W cannot be selected**.
- Starting at zero, the first nonzero selectable value appears to be **99 W** (owner's observation), which may correspond to **raw 1**.
- The app therefore appears to expose **approximately 1%-step values on a 9900 W full-scale**, with UI rounding or a nonuniform conversion. Mapping **100→9900** is supported by observed app + raw reading; **99→9800**, **1→99**, **0→0** are plausible but require direct paired app/Modbus tests.
- Do not assume a blanket 100 W step or naïve `raw * 100 W`. For example, 99% of 9900 is 9801 W, not 9800 W, indicating UI rounding or quantization may occur.
- **Do not implement writable watts→raw conversion until multiple points (0%, 1%, 50%, 99%, 100%) are observed** on the owner's inverter with read-only Modbus before/after app changes. On a real inverter also validate charge-side scaling separately.


## Correction from owner: midrange selection is quantized

The previous illustrative **4950 W** value should NOT be treated as an accepted app input. The owner reports that eLEKeeper appears to accept **4900 W or 5000 W**, not 4950 W. This is still an observation pending paired app/Modbus test. The earlier suggestion that 50% necessarily displays as 4950 W was unjustified. Preserve exactly observed 9900 W ↔ raw 100; test other specific accepted inputs rather than deriving the UI scale from percentage arithmetic. Do not enforce exact step sizes without verification.

## Clarification: TOU unscheduled fallback and controlled app-only test (2026-11-01)

Owner clarified that at approximately 17:22 Sunday 2026-11-01 local time, the **only enabled** schedule was Wednesday 22:00–22:40 discharge (charge enable 0, discharge enable 1); no Sunday window existed. Owner's eLEKeeper workflow **requires selecting/enabling overall Time-of-use mode to edit schedules** and saving, then optionally returning overall mode to Self-consumption. The setting named *Non-charge/discharge time period settings* is **the fallback inside TOU mode outside all defined windows**, with Self-consumption and Standby choices. It is NOT a setting applied only when TOU is disabled. Existing Modbus fallback 0x365F returned 1, consistent with self-consumption fallback. Therefore, when TOU is selected outside Wednesday's window, expected behaviour is ordinary self-consumption; however actual activation/readback remains subject to propagation delay, independent controller interference, and accurate schedule verification. Proposed bounded, owner-operated test: confirm there are still no Sunday charge/discharge slots and fallback is Self-consumption; using official eLEKeeper only, change Wednesday discharge power 9900→9800 W, save with TOU enabled; read back 0x3604,0x361B,0x3647,0x365F after propagation, then return to Self-consumption if desired and verify mode 0. Do NOT transmit Modbus writes. Never imply no possible risk or assume five-minute propagation is guaranteed.

## Second paired real-world test — 9800 W app ↔ raw 98 (2026-11-01)

Owner used **eLEKeeper only** to change the existing Wednesday discharge slot from **9900 W** to **9800 W** and switched the operating mode back to Self-consumption. Then a **read-only** Modbus test returned:

- `0x3647` mode = **0** (Self-consumption restored).
- `0x361D` first discharge slot combined day/power word = **1122** = `0x0462`, where weekday mask **4** (unchanged Wednesday), raw power low byte **98**.
- `0x365F` TOU unscheduled fallback = **1** (Self-consumption, unchanged).

**Observed pairs:**
| eLEKeeper discharge power | Actual raw low byte | Combined word with weekday mask 4 |
|---|---:|---:|
| 9900 W | 100 | 1124 |
| 9800 W | 98 | 1122 |

**Important:** 9800 W→98 disproves previous guess of 9800→99; 9900 W→100 is also not consistent with a blanket power_w = raw × 100 W. Device-side conversion may have special maximum/capping or UI-specific semantics; **do not interpolate or encode writable power from only these two points**. Future app-only test at 9700 W or a midrange point can narrow the mapping. Also possible firmware clamp/special 100 sentinel for max; not confirmed.

The owner has demonstrated that a schedule setting can be edited using eLEKeeper (while briefly in TOU) and returned to mode 0, leaving the scheduled weekday stored while not currently running. This tests readback correspondence, not real discharge effectiveness.

No Modbus writes performed; this repository's control implementation remains non-writing.

## Correction and breakthrough: app RE-READ shows 9702 W for raw 98 (2026-11-01)

**Important correction to the previous paired test:** User initially entered/reported `9800 W` while changing the schedule in the SAJ app, but on reopening the app **the actually saved/displayed power was `9702 W`**, while read-only Modbus was `0x361D = 1122 = (weekday mask 4 << 8) + power raw 98`. Therefore the prior row `9800 W ↔ raw 98` describes a **requested input**, NOT a confirmed stored app setting; it is erroneous if presented as a confirmed pair. The saved/confirmed value is **9702 W ↔ raw 98**.

Combined with original `9900 W ↔ raw 100` and owner's reported first nonzero `99 W`, the simple relation **displayed power W = Modbus power raw × 99** now fits all currently observed *stored* data:
- raw 100 → 9900 W (confirmed saved in app);
- raw 98 → 9702 W (confirmed saved in app);
- raw 1 → 99 W (app minimum reported, raw pairing not independently read).
Predicted, not yet tested: raw 99 → 9801 W; raw 50 → 4950 W.

The app may **quantize, floor, round or normalize entered watts when saved and read back**; exact input handling is unverified. Do not conclude the UI permits arbitrary `9800 W` or implement a rounding rule without testing. Previous assumptions about being able to choose only 4900/5000 and not 4950 may reflect the input widget or the save-time normalization; check future official-app readback.

**Developer action:** use `W = raw * 99` as the leading *read-only display hypothesis* for discharge on this 10 kW installation, but **do not authorize writes or apply this blindly to charge schedules** without additional paired confirmation at another point, power-limit validation and firmware-specific hardware testing. Do not ask user to set 9700 W based on earlier incorrect belief the confirmed saved value was 9800 W.

## Owner's explanation of app input versus device readback (2026-11-01)

User observes that eLEKeeper's editing field appears to accept **multiples of 100 W** but **normalizes/quantizes the value to a whole-number device power percentage on Save**, then replaces the input field with the canonical power calculated from the stored value. The confirmed case is input **9800 W** → Modbus raw **98** → reopened app **9702 W** (98 × 99). The confirmed maximum is **9900 W** → raw **100** → reopened app **9900 W**.

**Important nuance:** This does NOT demonstrate rounding to the nearest whole percent: 9800/9900×100≈98.99, for which nearest would be 99 (9801 W), yet observed raw 98. **Floor/truncation** of 9800/9900×100 would yield 98 (9702 W), matching observation; still only a hypothesis. Preserve exact observed raw percentage as the canonical device state for later HA sync. UI may show both input draft watts and canonical stored watts, clearly distinguishing them. A schedule should never be continually rewritten just to match its pre-save requested watt input, otherwise competing apps may oscillate.

Before writes: verify another 100 W input pair and separate charge-side power scaling and firmware behavior. No hardware writes are authorized.

## Third paired test — 5000 W entered and TOU mode active (2026-11-01)

Owner selected **Time-of-Use mode** in official eLEKeeper and entered **5000 W** in existing Wednesday 22:00–22:40 discharge slot. Did not return to Self-consumption before read. Read-only Modbus subsequently reported:

- **0x3647 = 1** — current overall mode **Time-of-Use** (confirmed first mode 1 readback).
- **0x361D = 1074** = 0x0432, weekday mask **4** (Wednesday), stored raw schedule power **50**.
- **0x3604 = 0** — no charge schedules enabled.
- **0x3605 = 1** — one discharge schedule enabled.
- **0x365F = 1** — outside-window fallback **Self-consumption**.

This confirms app input of 5000 W produces **raw 50**, but we have **NOT yet observed the app's refreshed/reopened canonical displayed watts**. Hypothesis W = raw × 99 predicts **4950 W**. Ask owner to reopen the discharge schedule and report whether it displays 4950 W (do not adjust or save again).

Observed raw pairs: app originally displayed 9900 W → 100; app reopened 9702 W → 98; user input 5000 W → 50. Device-side mode 1 and fallback 1 coexist; there was no enabled Sunday schedule in the earlier configuration. This tests configuration readback only, **not** whether scheduled battery discharge starts/stops correctly or safe direct Modbus writes.

Do NOT assert live time-of-use control integration is implemented; there are still no hardware control writes from Home Assistant. Keep the owner informed of remaining uncertainties and avoid unapproved mode changes.
