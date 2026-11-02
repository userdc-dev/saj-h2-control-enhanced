# Developer handover addendum — VPP SOC readback (v0.5.25)

Date: 2026-11-02. Applies to SAJ H2 Control Enhanced.

## Problem

A connected inverter showed **"Recent battery state of charge is unavailable"** during read-only VPP preflight. The controller previously relied on `sensor.saj_h2_safe_monitor_battery_state_of_charge` and a 90-second Home Assistant `last_updated` check. Renamed sensors or unchanged SOC values caused false missing readings.

## Change

- `custom_components/saj_h2_control_enhanced/vpp_soc_readback.py` performs two fresh **read-only** Modbus holding-register reads (function 03) of `0x406F` using the existing connected client and device ID.
- SOC is scaled by 0.01; raw 0–10000 represents 0–100%. Both replies must be valid and within 1 percentage point. The most recent verified value is used.
- `_fresh_vpp_preflight()` uses the helper for both **Preview** and **Start safety rehearsal**, under the existing shared command lock, with no dependency on any Home Assistant sensor entity ID.
- Failed or contradictory SOC reads return an unavailable result that **blocks** the proposed action. The UI shows the measured SOC or a diagnostic in the expanded preflight details.
- Added `tests/test_vpp_soc_readback.py` and mock-frontend assertions; CI includes these checks. Cache-busting frontend path: `/saj-h2-tou/v0525/`.

## Unchanged safety contract

The 95% charging guard and 10% discharge reserve remain unchanged. Live VPP charge/discharge remains disabled. No Modbus writes, TOU changes, curtailment, pricing changes, energy sensor renames or saved schedule resets were introduced.

The release was tested offline in GitHub Actions; verify SOC against the SAJ/elekeeper app on the actual inverter after deployment. Do not treat a passing preflight as permission to enable real VPP dispatch.
