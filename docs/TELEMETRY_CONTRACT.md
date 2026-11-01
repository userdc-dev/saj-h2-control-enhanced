# Telemetry contract for future time-of-use controls

**Status:** analysis and offline validation only. No Home Assistant integration binding and no inverter writes.

## Source of truth

Use numeric Home Assistant sensors produced by the independent read-only
`userdc-dev/saj-h2-safe-enhanced` integration. They are NOT mere display helpers.
Their measured states are inputs to all future validation and readback.

| Input key | Existing Home Assistant entity | Units | Role |
|---|---|---|---|
| soc_pct | `sensor.saj_h2_safe_monitor_battery_state_of_charge` | % | State and future charge/discharge limits |
| stored_kwh | `sensor.saj_h2_safe_monitor_estimated_battery_energy` | kWh | Informational; estimated from 40 kWh × SOC |
| battery_w | `sensor.saj_h2_safe_monitor_battery_power` | W | Negative means charging; positive discharging |
| battery_activity | `sensor.saj_h2_safe_monitor_battery_activity` | text | Supporting indication; never sole proof of action |
| mode | `sensor.saj_h2_safe_monitor_operating_mode` | text | 0 self-consumption; 1 time-of-use; 2 and 3 forbidden for command |
| solar_w | `sensor.saj_h2_safe_monitor_total_solar_power` | W | Real-time PV production, PV1+PV2+PV3 |
| home_w | `sensor.saj_h2_safe_monitor_home_consumption` | W | Home load |
| grid_w | `sensor.saj_h2_safe_monitor_grid_power_raw_signed` | W | Signed raw grid; direction unverified |
| battery_temp_c | `sensor.saj_h2_safe_monitor_battery_temperature` | °C | Monitoring and tentative safety checks |
| battery_voltage_v | `sensor.saj_h2_safe_monitor_battery_voltage` | V | Monitor only; not a BMS permission signal |

All IDs are default names observed in the user's HA. Verify at installation if entity
IDs were renamed. **Do not create substitute raw Modbus pollers** in the control
integration without a strong reason: concurrent/duplicate polling is a source of errors.

## Data consistency, heartbeat and anti-staleness

- The safe integration's live Modbus coordinator polls around **10 seconds**;
  operating mode and cumulative totals only around **60 seconds**.
- `last_changed` and `last_updated` for a Home Assistant state are **NOT**
  evidence of a successful recent Modbus poll: values can remain unchanged for
  hours during normal operation. `last_reported` may work in some HA versions
  but is not a substitute for a verified end-to-end source heartbeat.
- We **do not yet have a confirmed exposed successful-Modbus-poll timestamp**.
  The separate control project will not enable charge/discharge until a reliable
  heartbeat becomes available from the read-only system or another independently
  verified source. The monitor's internal `DataUpdateCoordinator.last_update_success`
  is relevant but **is not itself exposed as a public entity**.
- If the heartbeat stops, values become unavailable, or data cannot be
  correlated with recent readback, reject starting an operation. If active,
  attempt only a verified-safe stop mechanism; if that is unavailable, no
  hardware deployment should occur.
- Validate units, finite values, reasonable bounds, mode codes and the actual
  observed battery direction. Never treat missing data as 0 W.
- Entity state changes can be out of sync by a few seconds: an instantaneous
  power-balance mismatch is **not** sufficient proof of fault or control success.
- The `grid_import` / `grid_export` derived sensors are **unverified direction**
  and cannot yet justify battery-to-grid export or billing optimizations.
- The forecast entities are predictions and **must never** authorize a battery
  charge/discharge without verified real-time safety state.

## Control-relevant data not yet available

Before any write, obtain and validate:
- Exact H2 inverter + BMS firmware/profile and controller ownership.
- Real BMS charge/discharge permission, max allowable charge/discharge watts/amps
  *at the present SOC/temperature*, protection states and reserves.
- Whether any external SAJ/third-party controller owns or will override mode.
- Exact supported command registers, scaling, legal range, watchdog, readback,
  stop/release/restore semantics.
- Grid compliance/export permissions and their interactions with discharge.

**Hard rule:** Mode 2 Backup and Mode 3 Off-grid/Passive must never be sent,
even as a temporary safety test, reset, or restoration command.

## Code status

`control_core/telemetry.py` parses a plain dictionary of states into a
validated snapshot. `control_core/planner.py` reviews requested duration and
direction. Both are offline pure-Python modules and **do not** connect to HA,
create entities, invoke service calls or write Modbus. All review results set
`allowed_to_execute=False` until the hardware and safety milestones are
independently completed and approved.

Run offline tests: `python -m unittest discover -s tests -p 'test_telemetry.py'`.
