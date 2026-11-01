# SAJ H2 Control Enhanced v0.2.0 — dynamic TOU dashboard preview

**Status: committed and GitHub CI-tested; NOT installed on the user's Kamrui Home Assistant yet.**

## What v0.2.0 adds

- Dedicated **SAJ TOU Control** dashboard (separate from existing SAJ Energy) created if absent when the control integration starts; existing dashboards are NEVER overwritten.
- Embedded `custom:saj-tou-dynamic-card` served from the integration's `frontend/` folder. It is automatically registered on startup; no separate `/config/www` copy required.
- Auto-discovery of configured `saj_h2_safe` monitoring entries in the **Add Integration** setup flow; select the existing SAJ device rather than typing its IP. If no monitor is configured, manual IP setup remains available. Existing installations' host matches can follow the matching safe monitor.
- Auto-discovery of TOU **entities and devices** by stable `saj_tou_entry_id` and `saj_tou_role` sensor attributes. The card updates when entity IDs are renamed, when device mode/schedule changes in eLEKeeper, and when a different TOU device is selected.
- Up to **7 charge** and **7 discharge** schedule rows; zero schedules is perfectly valid. Add/remove preview rows, 24-hour start/end inputs, seven weekday toggles and 0–100 raw-percent sliders. Local previews only.
- Live device readback for global mode, outside-schedule fallback, schedule count, stored times, weekday raw mask and power.
- Discharge preview watts = `raw × 99` confirmed for this inverter. **Charging watts mapping and weekday bit positions apart from Wednesday mask 4 are not yet verified.** No guesses are displayed as verified.
- When eLEKeeper changes a device setting, the **device readback display always refreshes**. Untouched local preview inputs follow the updated device; edited drafts are preserved with a warning and a **Reload draft from inverter** button.
- UI Apply button is **disabled**. No charge/discharge, scheduler, backup, off-grid or Modbus write functions exist.

## Update the existing installation safely

The user already has v0.1.x installed as a **separate** device named `SAJ H2 TOU Readback` alongside `SAJ H2 Safe Monitor`.

**Do not delete either integration, change entity IDs, or replace the SAJ Energy dashboard.**

As root on Kamrui, copy the new control files **over the existing control component folder**:

```bash
curl -fL https://github.com/userdc-dev/saj-h2-control-enhanced/archive/refs/heads/main.tar.gz -o /tmp/saj-tou-update.tar.gz && mkdir -p /tmp/saj-tou-update && tar -xzf /tmp/saj-tou-update.tar.gz -C /tmp/saj-tou-update && cp -a /tmp/saj-tou-update/saj-h2-control-enhanced-main/custom_components/saj_h2_control_enhanced/. /home/kamrui/compose-files/homeassistant/config/custom_components/saj_h2_control_enhanced/
```

Then separately run `docker restart homeassistant`.

After restarting, look for **SAJ TOU Control** in the HA sidebar. The card detects the installed TOU devices. If the dashboard did not auto-create due to an unsupported Home Assistant API, add a **Manual card** with YAML:

```yaml
type: custom:saj-tou-dynamic-card
```

Check Home Assistant logs for `Automatic SAJ TOU dashboard creation unavailable` if dashboard auto-creation did not work. The frontend card is served by the integration at `/saj-h2-tou/saj-tou-dynamic-card.js?v=020`. If script auto-registration failed, you may manually register that as a JavaScript module under Settings → Dashboards → Resources. Refresh the browser afterward.

### Preview screen contents

- Operating mode selector (Self-consumption / Time-of-use): local draft only.
- Outside TOU window fallback selector (Self-consumption / Standby): local draft only.
- Charge schedule cards (0–7) with time, day selector and 0–100% preview sliders (no unverified W display).
- Discharge schedule cards (0–7) with 24h time, day selector and watts computed from raw%.
- Actual saved state from inverter remains visibly separate from unsaved changes.
- Reset preview from live inverter state, clearly disabled Apply action.

### How dynamic sync works

The HA integration polls **read-only Modbus register snapshots**. Its sensor states carry `saj_tou_role` and `saj_tou_entry_id`. The browser card finds devices through those attributes and locates the right mode and schedule entities irrespective of custom entity ID names. It does **not** guess slot counts, create fake active schedules, or invent charge watt conversion. External eLEKeeper changes become visible after the inverter and HA polling publish new readings; expect the app's observed up-to-five-minute activation delay, plus HA's polling interval (120s by default).

### What's not done

- The editable previews do not save, persist through page reload, or issue actual inverter commands.
- The per-weekday Modbus mapping beyond confirmed Wednesday and charge power scaling are still unverified.
- A card cannot establish actual physical charging/discharging solely from stored schedules.
- The new automatic dashboard mechanism uses Home Assistant's storage-dashboard API, which may vary by HA release; if unsupported, it fails gracefully without modifying existing dashboards.
- No physical write tests or end-to-end browser checks on the user's HA have been performed for v0.2.0. GitHub CI confirms Python syntax, offline decoder/safety tests and JavaScript syntax only.

**Safety:** No writable registers, modes 2/3 never offered, no settings changed on the physical inverter. See [Safety roadmap](SAFETY_AND_ROADMAP.md), [Developer handoff](../DEVELOPER_HANDOFF.md).
