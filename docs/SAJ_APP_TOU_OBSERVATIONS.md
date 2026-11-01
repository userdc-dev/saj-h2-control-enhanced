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
