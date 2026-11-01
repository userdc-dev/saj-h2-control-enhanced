# Read-only TOU integration preview (v0.1.0)

The new separate Home Assistant integration lives under `custom_components/saj_h2_control_enhanced`.

**No Modbus writes. No control services.** It reads saved SAJ H2 Time-of-Use settings using function 03: register blocks `0x3604` (23 words), `0x361B` (21 words), operating mode `0x3647`, and outside-schedule fallback `0x365F`. It re-reads the slot enable masks and mode before accepting a snapshot. Polling defaults to 120 seconds.

## Install on Debian Kamrui

1. Download the `main` branch archive of `userdc-dev/saj-h2-control-enhanced`.
2. Copy **only** `custom_components/saj_h2_control_enhanced` into Home Assistant config path `/home/kamrui/compose-files/homeassistant/config/custom_components/`.
3. Restart the `homeassistant` Docker container.
4. In Home Assistant Settings → Devices & Services → Add Integration, search for **SAJ H2 Control Enhanced (Read-only TOU Preview)**.
5. Configure the inverter LAN IP, port 502 and scan interval 120s, same address as the existing read-only safe monitor.

The existing `saj_h2_safe` monitor must remain installed, unchanged. Avoid aggressive polling with multiple Modbus clients.

## New sensors

- Operating mode, read from the inverter.
- Outside schedule behaviour: Self-consumption or Standby.
- Enabled charge schedules (0–7).
- Enabled discharge schedules (0–7).
- Charge schedules: a count and an attribute with up to 7 active rows, including raw power percentages (charge W conversion still not confirmed).
- Discharge schedules: a count and an attribute with up to 7 active rows, with discharge W displayed as raw × 99 based on paired eLEKeeper tests.
- TOU device sync: last successful snapshot, changes detected since startup, and explicit read-only status.

These settings are read **from the device**, not fake dashboard helpers. Schedule attributes include start, end, raw weekday mask and raw percentage.

## Test

Confirm current readings against official eLEKeeper: earlier observed 1 discharge on Wednesday 22:00–22:40, input 5000W saved as 4950W / raw 50; Time-of-Use mode 1; unscheduled Self-consumption fallback 1. If the app changed since then, use its new saved settings. Later change an app setting; allow its observed up-to-five-minute propagation, verify HA state and change count. The integration shows stored settings, not proof that scheduled power is actually flowing.

A Modbus failure makes sensors unavailable; this is preferable to falsely claiming synchronization. No writable controls should be built until power and weekday maps, controller ownership, safe stop and hardware limits are verified.

## Rollback

Remove the new integration from Home Assistant Devices & Services. If needed, remove only the `saj_h2_control_enhanced` directory and restart Home Assistant. Never delete the `saj_h2_safe` component.
