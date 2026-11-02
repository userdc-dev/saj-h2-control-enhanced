"""SAJ H2 control integration: read-only polling and explicit supervised writes.

The coordinator only reads device settings. Mode, fallback and schedule writes
are separately registered Home Assistant actions, requiring user interaction,
preflight checks, and post-write verification. No automatic inverter writes.
"""
from datetime import datetime, timedelta, timezone
import inspect
import asyncio
import logging

import voluptuous as vol

from homeassistant.core import HomeAssistant, SupportsResponse
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from pymodbus.client import AsyncModbusTcpClient

from .const import DEFAULT_SCAN_INTERVAL, UNIT_ID, DOMAIN
from .tou_protocol import (
    CHARGE_START, CHARGE_COUNT, DISCHARGE_START, DISCHARGE_COUNT,
    MODE_ADDR, FALLBACK_ADDR, decode_config, InvalidTOUData,
    active_signature, describe_changes,
)

_LOGGER = logging.getLogger(__name__)
PLATFORMS = ("sensor",)


async def async_setup(hass: HomeAssistant, config):
    """Register dynamic frontend resource, once per HA process."""
    from .frontend_setup import async_register_frontend
    await async_register_frontend(hass)

    async def preview_mode_change(call):
        """Force a fresh readback and return a dry-run, never an inverter write."""
        target = call.data["target_mode"]
        entries = [
            entry for entry in hass.config_entries.async_entries(DOMAIN)
            if getattr(entry, "runtime_data", None) is not None
        ]
        requested_id = call.data.get("entry_id")
        if requested_id:
            entries = [entry for entry in entries if entry.entry_id == requested_id]
        if len(entries) != 1:
            raise vol.Invalid(
                "Specify entry_id if multiple SAJ control entries are configured "
                "(or finish integration setup if none)")
        coordinator = entries[0].runtime_data
        await coordinator.async_request_refresh()
        if not coordinator.last_update_success or not coordinator.data:
            raise vol.Invalid("Live Modbus readback failed; preview refused")
        config = coordinator.data["config"]
        if config.mode not in (0, 1):
            raise vol.Invalid("Inverter is in an unsupported operating mode")
        if config.fallback not in (0, 1):
            raise vol.Invalid("Outside-TOU fallback code is unsupported")
        if not 0 <= config.charge_mask <= 127 or not 0 <= config.discharge_mask <= 127:
            raise vol.Invalid("Unrecognized schedule enable bits")
        if sum(s.enabled for s in config.charge_slots) != config.charge_mask.bit_count():
            raise vol.Invalid("Charge slot mask inconsistent")
        if sum(s.enabled for s in config.discharge_slots) != config.discharge_mask.bit_count():
            raise vol.Invalid("Discharge slot mask inconsistent")
        return {
            "status": "DRY_RUN_ONLY",
            "write_sent": False,
            "inverter_mode_raw": config.mode,
            "requested_mode_raw": {"self_consumption": 0, "time_of_use": 1}[target],
            "change_needed": config.mode != {
                "self_consumption": 0, "time_of_use": 1}[target],
            "fallback_raw": config.fallback,
            "charge_enable_mask": config.charge_mask,
            "discharge_enable_mask": config.discharge_mask,
            "device_read_at": coordinator.data["timestamp"].isoformat(),
            "message": "Preview checked live inverter state. No settings changed.",
        }

    hass.services.async_register(
        DOMAIN, "preview_mode_change", preview_mode_change,
        schema=vol.Schema({
            vol.Required("target_mode"): vol.In(
                ("self_consumption", "time_of_use")),
            vol.Optional("entry_id"): str,
        }),
        supports_response=SupportsResponse.ONLY,
    )
    async def preview_schedule_change(call):
        """Validate one edited existing slot against a fresh double-read."""
        entries = [
            entry for entry in hass.config_entries.async_entries(DOMAIN)
            if getattr(entry, "runtime_data", None) is not None
        ]
        requested_id = call.data.get("entry_id")
        if requested_id:
            entries = [entry for entry in entries if entry.entry_id == requested_id]
        if len(entries) != 1:
            raise vol.Invalid("Exactly one SAJ TOU control integration required")
        coordinator = entries[0].runtime_data
        await coordinator.async_request_refresh()
        if not coordinator.last_update_success or not coordinator.data:
            raise vol.Invalid("Fresh double-read unavailable; preview refused")
        from .schedule_preview import (
            preview_existing_slot, SlotValue, SchedulePreviewError,
        )
        d = call.data
        try:
            return preview_existing_slot(
                coordinator.data["config"],
                direction=d["direction"], slot_number=d["slot"],
                expected=SlotValue(
                    d["expected_start"], d["expected_end"],
                    d["expected_day_mask"], d["expected_power_percent"],
                ),
                new_start=d["start"], new_end=d["end"],
                days=d["weekdays"], power_percent=d["power_percent"],
            )
        except SchedulePreviewError as exc:
            raise vol.Invalid(str(exc)) from exc

    hass.services.async_register(
        DOMAIN, "preview_schedule_change", preview_schedule_change,
        schema=vol.Schema({
            vol.Required("direction"): vol.In(("charge", "discharge")),
            vol.Required("slot"): vol.All(vol.Coerce(int), vol.Range(min=1, max=7)),
            vol.Required("expected_start"): str,
            vol.Required("expected_end"): str,
            vol.Required("expected_day_mask"): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=127)),
            vol.Required("expected_power_percent"): vol.All(
                vol.Coerce(int), vol.Range(min=0, max=100)),
            vol.Required("start"): str,
            vol.Required("end"): str,
            vol.Required("weekdays"): [vol.In(("Mon", "Tue", "Wed", "Thu", "Fri"))],
            vol.Required("power_percent"): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=100)),
            vol.Optional("entry_id"): str,
        }),
        supports_response=SupportsResponse.ONLY,
    )

    async def schedule_transaction_action(call, *, perform_write=False):
        """Full 7+7 slot plan; only explicit confirmation may reach Modbus writes."""
        entries = [
            e for e in hass.config_entries.async_entries(DOMAIN)
            if getattr(e, "runtime_data", None) is not None
        ]
        wanted = call.data.get("entry_id")
        if wanted:
            entries = [e for e in entries if e.entry_id == wanted]
        if len(entries) != 1:
            raise vol.Invalid("Select exactly one SAJ control device")
        coordinator = entries[0].runtime_data
        from .schedule_transaction import (
            read_full, build_plan, execute_plan, ScheduleTransactionError,
        )
        d = call.data
        arguments = {
            "expected_charge":d["expected_charge"],
            "expected_discharge":d["expected_discharge"],
            "proposed_charge":d["proposed_charge"],
            "proposed_discharge":d["proposed_discharge"],
        }
        # Manual schedules and mode switches share exactly one lock.
        async with pilot_lock:
            try:
                if perform_write:
                    host,port = coordinator._connection_details()
                    result = await execute_plan(
                        host=host, port=int(port),
                        confirmation=d["confirmation"],
                        device_model=d["device_model"],
                        control_firmware=d["control_firmware"],
                        **arguments,
                    )
                else:
                    host,port = coordinator._connection_details()
                    client = AsyncModbusTcpClient(
                        host,port=int(port),timeout=5,retries=0,
                    )
                    try:
                        if not await client.connect():
                            raise ScheduleTransactionError(
                                "Cannot connect for fresh schedule read")
                        snap = await read_full(client)
                    finally:
                        client.close()
                    result = build_plan(snap,**arguments).summary()
                await coordinator.async_request_refresh()
                return result
            except ScheduleTransactionError as exc:
                raise vol.Invalid(
                    str(exc) + (
                        "; do not repeat if any write may have been sent"
                        if perform_write else "; reload stale draft"
                    )
                ) from exc

    _schedule_data_fields = {
        vol.Required("expected_charge"): list,
        vol.Required("expected_discharge"): list,
        vol.Required("proposed_charge"): list,
        vol.Required("proposed_discharge"): list,
        vol.Optional("entry_id"): str,
    }
    async def plan_schedules(call):
        return await schedule_transaction_action(call, perform_write=False)

    async def apply_schedules(call):
        return await schedule_transaction_action(call, perform_write=True)

    hass.services.async_register(
        DOMAIN, "plan_schedules",
        plan_schedules,
        schema=vol.Schema(_schedule_data_fields),
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN, "apply_schedules",
        apply_schedules,
        schema=vol.Schema({
            **_schedule_data_fields,
            vol.Required("confirmation"): vol.In(
                ("I AUTHORIZE TOU SCHEDULE CHANGES",)),
            vol.Required("device_model"): vol.In(("H2-10K-S3-A",)),
            vol.Required("control_firmware"): vol.In(("v2.018",)),
        }),
        supports_response=SupportsResponse.ONLY,
    )

    # Manual, single-shot hardware pilot: NOT invoked from dashboards or polls.
    # This separate action requires a literal confirmation and exact old mode.
    pilot_lock = asyncio.Lock()

    async def supervised_outside_tou_fallback(call):
        """Single confirmed outside-TOU setting change; no other registers written."""
        if pilot_lock.locked():
            raise vol.Invalid("Another supervised inverter command is running")
        entries = [
            e for e in hass.config_entries.async_entries(DOMAIN)
            if getattr(e, "runtime_data", None) is not None
        ]
        selected = call.data.get("entry_id")
        if selected:
            entries = [e for e in entries if e.entry_id == selected]
        if len(entries) != 1:
            raise vol.Invalid("Exactly one matching SAJ TOU control device required")
        from .supervised_fallback import run_fallback_control, FallbackWriteError
        coordinator = entries[0].runtime_data
        host, port = coordinator._connection_details()
        async with pilot_lock:
            try:
                result = await run_fallback_control(
                    host=host, port=int(port),
                    target=call.data["target_fallback"],
                    expected_fallback=call.data["expected_fallback"],
                    expected_mode=call.data["expected_mode"],
                    standby_confirmation=call.data.get("standby_confirmation"),
                    device_model=call.data["device_model"],
                    control_firmware=call.data["control_firmware"],
                )
                await coordinator.async_request_refresh()
                return result
            except FallbackWriteError as exc:
                raise vol.Invalid(
                    str(exc) + "; do not repeat a possibly sent command"
                ) from exc

    hass.services.async_register(
        DOMAIN, "supervised_outside_tou_fallback",
        supervised_outside_tou_fallback,
        schema=vol.Schema({
            vol.Required("target_fallback"): vol.In((0,1)),
            vol.Required("expected_fallback"): vol.In((0,1)),
            vol.Required("expected_mode"): vol.In((0,1)),
            vol.Required("device_model"): vol.In(("H2-10K-S3-A",)),
            vol.Required("control_firmware"): vol.In(("v2.018",)),
            vol.Optional("standby_confirmation"): vol.In(
                ("I CONFIRM STANDBY OUTSIDE TOU",)),
            vol.Optional("entry_id"): str,
        }),
        supports_response=SupportsResponse.ONLY,
    )

    async def supervised_friday_charge_time_pilot(call):
        """One explicitly authorized 21:30–22:00 Friday charging test."""
        if pilot_lock.locked():
            raise vol.Invalid("Another supervised inverter control is in progress")
        entries = [
            e for e in hass.config_entries.async_entries(DOMAIN)
            if getattr(e, "runtime_data", None) is not None
        ]
        requested_id = call.data.get("entry_id")
        if requested_id:
            entries = [e for e in entries if e.entry_id == requested_id]
        if len(entries) != 1:
            raise vol.Invalid("Exactly one matching SAJ control entry is required")
        coordinator = entries[0].runtime_data
        from .supervised_schedule_write import (
            run_friday_charge_time_pilot, ScheduleWriteError,
        )
        host, port = coordinator._connection_details()
        async with pilot_lock:
            try:
                result = await run_friday_charge_time_pilot(
                    host=host, port=int(port),
                    confirmation=call.data["confirmation"],
                    device_model=call.data["device_model"],
                    control_firmware=call.data["control_firmware"],
                )
                await coordinator.async_request_refresh()
                return result
            except ScheduleWriteError as exc:
                raise vol.Invalid(
                    str(exc) + "; do not repeat a possibly partial write"
                ) from exc

    hass.services.async_register(
        DOMAIN, "supervised_friday_charge_time_pilot",
        supervised_friday_charge_time_pilot,
        schema=vol.Schema({
            vol.Required("confirmation"): vol.In(
                ("I AUTHORIZE FRIDAY CHARGE TIME TEST",)),
            vol.Required("device_model"): vol.In(("H2-10K-S3-A",)),
            vol.Required("control_firmware"): vol.In(("v2.018",)),
            vol.Optional("entry_id"): str,
        }),
        supports_response=SupportsResponse.ONLY,
    )

    async def supervised_tou_pilot(call):
        if pilot_lock.locked():
            raise vol.Invalid("A supervised mode test is already running")
        entries = [
            e for e in hass.config_entries.async_entries(DOMAIN)
            if getattr(e, "runtime_data", None) is not None
        ]
        requested_id = call.data.get("entry_id")
        if requested_id:
            entries = [e for e in entries if e.entry_id == requested_id]
        if len(entries) != 1:
            raise vol.Invalid("Exactly one matching SAJ control entry is required")
        coordinator = entries[0].runtime_data
        from .supervised_write import (
            run_supervised_tou_test, SupervisedWriteError,
        )
        host, port = coordinator._connection_details()
        async with pilot_lock:
            try:
                result = await run_supervised_tou_test(
                    host=host, port=port,
                    confirmed_phrase=call.data["confirmation"],
                    expected_mode=call.data["expected_current_mode"],
                    device_model=call.data["device_model"],
                    control_firmware=call.data["control_firmware"],
                )
                await coordinator.async_request_refresh()
                return result
            except SupervisedWriteError as exc:
                raise vol.Invalid(
                    str(exc) + "; don't retry automatically"
                ) from exc

    hass.services.async_register(
        DOMAIN, "supervised_tou_pilot", supervised_tou_pilot,
        schema=vol.Schema({
            vol.Required("confirmation"): vol.In(
                ("I AUTHORIZE ONE TOU MODE WRITE",)),
            vol.Required("expected_current_mode"): vol.In((0,)),
            vol.Required("device_model"): vol.In(("H2-10K-S3-A",)),
            vol.Required("control_firmware"): vol.In(("v2.018",)),
            vol.Optional("entry_id"): str,
        }),
        supports_response=SupportsResponse.ONLY,
    )
    async def supervised_self_consumption_pilot(call):
        """Reverse direction has distinct explicit confirmation and no dashboard shortcut."""
        if pilot_lock.locked():
            raise vol.Invalid("A supervised mode test is already running")
        entries = [
            e for e in hass.config_entries.async_entries(DOMAIN)
            if getattr(e, "runtime_data", None) is not None
        ]
        requested_id = call.data.get("entry_id")
        if requested_id:
            entries = [e for e in entries if e.entry_id == requested_id]
        if len(entries) != 1:
            raise vol.Invalid("Exactly one matching SAJ control entry is required")
        coordinator = entries[0].runtime_data
        from .supervised_write import (
            run_supervised_tou_test, SupervisedWriteError,
        )
        host, port = coordinator._connection_details()
        async with pilot_lock:
            try:
                result = await run_supervised_tou_test(
                    host=host, port=port,
                    confirmed_phrase=call.data["confirmation"],
                    expected_mode=1,
                    target_mode=0,
                    device_model=call.data["device_model"],
                    control_firmware=call.data["control_firmware"],
                )
                await coordinator.async_request_refresh()
                return result
            except SupervisedWriteError as exc:
                raise vol.Invalid(
                    str(exc) + "; don't retry automatically"
                ) from exc

    hass.services.async_register(
        DOMAIN, "supervised_self_consumption_pilot",
        supervised_self_consumption_pilot,
        schema=vol.Schema({
            vol.Required("confirmation"): vol.In(
                ("I AUTHORIZE ONE SELF CONSUMPTION MODE WRITE",)),
            vol.Required("device_model"): vol.In(("H2-10K-S3-A",)),
            vol.Required("control_firmware"): vol.In(("v2.018",)),
            vol.Optional("entry_id"): str,
        }),
        supports_response=SupportsResponse.ONLY,
    )
    # The VPP safety supervisor is a durable, read-only rehearsal engine.
    # The global lock serializes all direct TOU writes and double-read checks.
    # NO service in this section may issue a Modbus write.
    hass.data.setdefault(DOMAIN,{})["pilot_lock"] = pilot_lock

    def _vpp_entry(data):
        entries=[
            e for e in hass.config_entries.async_entries(DOMAIN)
            if getattr(e,"runtime_data",None) is not None and
            (not data.get("entry_id") or e.entry_id==data["entry_id"])
        ]
        if len(entries)!=1:
            raise vol.Invalid("Select exactly one configured SAJ control inverter")
        return entries[0]

    async def _fresh_vpp_preflight(data):
        """Caller MUST hold pilot_lock before invoking this Modbus double-read."""
        entry=_vpp_entry(data)
        coordinator=entry.runtime_data
        from .schedule_transaction import read_full, ScheduleTransactionError
        from .vpp_quick_preview import preview_dispatch
        from zoneinfo import ZoneInfo

        host,port=coordinator._connection_details()
        client=AsyncModbusTcpClient(host,port=int(port),timeout=5,retries=0)
        try:
            if not await client.connect():
                raise vol.Invalid("Cannot reach inverter for VPP double-read")
            snapshot=await read_full(client)
            soc_state=hass.states.get(
                "sensor.saj_h2_safe_monitor_battery_state_of_charge"
            )
            soc=None
            if soc_state:
                try:
                    reading_time=getattr(soc_state,"last_updated",None)
                    age=(datetime.now(timezone.utc)-reading_time).total_seconds()
                    if 0 <= age <= 90:
                        soc=float(soc_state.state)
                except (TypeError,ValueError,AttributeError):
                    pass
            preview=preview_dispatch(
                snapshot[2],
                direction=data["direction"],
                duration_minutes=data["duration_minutes"],
                now=datetime.now(ZoneInfo(
                    hass.config.time_zone or "Australia/Adelaide"
                )),
                soc=soc,
            )
            return entry,snapshot,preview
        except ScheduleTransactionError as exc:
            raise vol.Invalid("VPP read-only preflight refused: "+str(exc)) from exc
        finally:
            client.close()

    async def preview_vpp_dispatch(call):
        async with pilot_lock:
            _,_,result=await _fresh_vpp_preflight(call.data)
            return result

    _vpp_preview_schema=vol.Schema({
        vol.Required("direction"):vol.In(("charge","discharge")),
        vol.Required("duration_minutes"):vol.All(
            vol.Coerce(int),vol.In((5,10,60))),
        vol.Optional("entry_id"):str,
    })
    hass.services.async_register(
        DOMAIN,"preview_vpp_dispatch",preview_vpp_dispatch,
        schema=_vpp_preview_schema,
        supports_response=SupportsResponse.ONLY,
    )

    async def vpp_rehearsal_status(call):
        entry=_vpp_entry(call.data)
        return entry.runtime_data.vpp_supervisor.status()

    hass.services.async_register(
        DOMAIN,"vpp_rehearsal_status",vpp_rehearsal_status,
        schema=vol.Schema({vol.Optional("entry_id"):str}),
        supports_response=SupportsResponse.ONLY,
    )

    async def start_vpp_safety_rehearsal(call):
        if call.data["confirmation"]!="SIMULATE ONLY - NO INVERTER WRITES":
            raise vol.Invalid("Literal simulation-only confirmation required")
        async with pilot_lock:
            entry,snapshot,preview=await _fresh_vpp_preflight(call.data)
            from .vpp_safety_supervisor import SupervisorError
            try:
                return await entry.runtime_data.vpp_supervisor.begin_rehearsal(
                    preview,snapshot)
            except SupervisorError as exc:
                raise vol.Invalid(str(exc)) from exc

    hass.services.async_register(
        DOMAIN,"start_vpp_safety_rehearsal",start_vpp_safety_rehearsal,
        schema=vol.Schema({
            vol.Required("direction"):vol.In(("charge","discharge")),
            vol.Required("duration_minutes"):vol.All(
                vol.Coerce(int),vol.In((5,10,60))),
            vol.Required("confirmation"):vol.In(
                ("SIMULATE ONLY - NO INVERTER WRITES",)),
            vol.Optional("entry_id"):str,
        }),
        supports_response=SupportsResponse.ONLY,
    )

    async def cancel_vpp_safety_rehearsal(call):
        from .vpp_safety_supervisor import SupervisorError
        async with pilot_lock:
            entry=_vpp_entry(call.data)
            try:
                return await entry.runtime_data.vpp_supervisor.cancel()
            except SupervisorError as exc:
                raise vol.Invalid(str(exc)) from exc

    hass.services.async_register(
        DOMAIN,"cancel_vpp_safety_rehearsal",cancel_vpp_safety_rehearsal,
        schema=vol.Schema({vol.Optional("entry_id"):str}),
        supports_response=SupportsResponse.ONLY,
    )

    async def verify_vpp_safety_baseline(call):
        """Manual no-write double-read; compare FULL raw TOU register words."""
        from .vpp_safety_supervisor import SupervisorError
        from .schedule_transaction import read_full, ScheduleTransactionError
        async with pilot_lock:
            entry=_vpp_entry(call.data)
            supervisor=entry.runtime_data.vpp_supervisor
            if supervisor.record.get("baseline") is None:
                raise vol.Invalid("No saved VPP baseline to verify")
            host,port=entry.runtime_data._connection_details()
            client=AsyncModbusTcpClient(
                host,port=int(port),timeout=5,retries=0)
            try:
                if not await client.connect():
                    raise vol.Invalid("Cannot connect for baseline verification")
                snapshot=await read_full(client)
                return await supervisor.verify_baseline(snapshot)
            except (ScheduleTransactionError,SupervisorError) as exc:
                raise vol.Invalid("Baseline verification refused: "+str(exc)) from exc
            finally:
                client.close()

    hass.services.async_register(
        DOMAIN,"verify_vpp_safety_baseline",verify_vpp_safety_baseline,
        schema=vol.Schema({vol.Optional("entry_id"):str}),
        supports_response=SupportsResponse.ONLY,
    )

    async def acknowledge_vpp_safety_warning(call):
        from .vpp_safety_supervisor import SupervisorError
        async with pilot_lock:
            entry=_vpp_entry(call.data)
            try:
                return await entry.runtime_data.vpp_supervisor.acknowledge()
            except SupervisorError as exc:
                raise vol.Invalid(str(exc)) from exc

    hass.services.async_register(
        DOMAIN,"acknowledge_vpp_safety_warning",
        acknowledge_vpp_safety_warning,
        schema=vol.Schema({vol.Optional("entry_id"):str}),
        supports_response=SupportsResponse.ONLY,
    )

    # Forecast settings update ONLY this HA config entry. Never touches Modbus.
    async def save_forecast_settings(call):
        import json
        from .forecast import validate_settings, settings_for
        matches = [
            e for e in hass.config_entries.async_entries(DOMAIN)
            if getattr(e, "runtime_data", None) is not None and
            (not call.data.get("entry_id") or e.entry_id == call.data["entry_id"])
        ]
        if len(matches) != 1:
            raise vol.Invalid("Select exactly one SAJ control device")
        selected = matches[0]
        try:
            groups = json.loads(call.data["groups_json"])
            groups, efficiency, ac_limit = validate_settings(
                groups, call.data["efficiency"], call.data["ac_limit_kw"])
        except (ValueError, TypeError) as exc:
            raise vol.Invalid(str(exc)) from exc
        from .forecast import SajEditableForecast
        opts = dict(selected.options)
        opts.update({
            "forecast_groups": groups,
            "forecast_efficiency": efficiency,
            "forecast_ac_limit_kw": ac_limit,
            "forecast_configured": True,
        })
        hass.config_entries.async_update_entry(selected, options=opts)
        forecast = getattr(selected.runtime_data, "editable_forecast", None)
        if forecast is not None:
            await forecast.async_request_refresh()
        return {"status": "FORECAST_SETTINGS_SAVED", "write_sent": False,
                "settings": settings_for(selected),
                "forecast_available": bool(forecast and forecast.last_update_success)}

    hass.services.async_register(
        DOMAIN, "save_forecast_settings", save_forecast_settings,
        schema=vol.Schema({
            vol.Required("groups_json"): str,
            vol.Required("efficiency"): vol.All(vol.Coerce(float), vol.Range(min=1, max=100)),
            vol.Required("ac_limit_kw"): vol.All(vol.Coerce(float), vol.Range(min=0.5, max=100)),
            vol.Optional("entry_id"): str,
        }),
        supports_response=SupportsResponse.ONLY,
    )
    # User-editable static tariff model: changes cost calculations only.
    async def save_cost_settings(call):
        from .energy_finance import validate_pricing
        matches=[
            e for e in hass.config_entries.async_entries(DOMAIN)
            if getattr(e,"runtime_data",None) is not None
            and (not call.data.get("entry_id") or e.entry_id==call.data["entry_id"])
        ]
        if len(matches)!=1:
            raise vol.Invalid("Select exactly one SAJ H2 control entry")
        selected=matches[0]
        try:
            import_rate,export_rate,supply=validate_pricing(
                call.data["import_rate"],call.data["export_rate"],
                call.data["daily_supply"])
        except ValueError as exc:
            raise vol.Invalid(str(exc)) from exc
        opts=dict(selected.options)
        opts.update({
            "import_rate":import_rate,"export_rate":export_rate,
            "daily_supply":supply,"currency":hass.config.currency or "AUD",
            "configured":True,
        })
        hass.config_entries.async_update_entry(selected,options=opts)
        accounting=getattr(selected.runtime_data,"energy_accounting",None)
        if accounting is not None:
            accounting.refresh_snapshot()
        return {
            "status":"COST_SETTINGS_SAVED","write_sent":False,
            "pricing":{k:opts[k] for k in
                       ("import_rate","export_rate","daily_supply","currency")},
        }

    hass.services.async_register(
        DOMAIN,"save_cost_settings",save_cost_settings,
        schema=vol.Schema({
            vol.Required("import_rate"):vol.Coerce(float),
            vol.Required("export_rate"):vol.Coerce(float),
            vol.Required("daily_supply"):vol.Coerce(float),
            vol.Optional("entry_id"):str,
        }),
        supports_response=SupportsResponse.ONLY,
    )
    # v0.5.16: complete TOU import/export tariff schedules, signed FiT,
    # explicit GST and other taxes. Only updates HA config-entry options and
    # read-only cost accounting; never accesses Modbus write functions.
    async def save_tariff_profile(call):
        import json
        from .tariffs import validate_profile
        matching=[
            e for e in hass.config_entries.async_entries(DOMAIN)
            if getattr(e,"runtime_data",None) is not None and
            (not call.data.get("entry_id") or
             e.entry_id==call.data["entry_id"])
        ]
        if len(matching)!=1:
            raise vol.Invalid("Select exactly one SAJ control entry")
        selected=matching[0]
        raw=call.data["profile_json"]
        if len(raw)>40000:
            raise vol.Invalid("Tariff setup exceeds maximum configuration size")
        try:
            profile=validate_profile(json.loads(raw))
        except (ValueError,TypeError,KeyError) as exc:
            raise vol.Invalid(f"Invalid time-of-use tariff: {exc}") from exc
        profile["configured"]=True
        profile["currency"]=hass.config.currency or profile["currency"]
        accounting=getattr(selected.runtime_data,"energy_accounting",None)
        if accounting is not None:
            # Keep the old ledger before installing a new revision.
            await accounting.async_save()
        revision=datetime.now(timezone.utc).isoformat()
        options=dict(selected.options)
        options["tariff_profile"]=profile
        options["tariff_revision"]=revision
        hass.config_entries.async_update_entry(selected,options=options)
        if accounting is not None:
            accounting.on_tariff_changed()
            # Persist today's full fixed daily supply charge immediately.
            await accounting.async_save()
        return {
            "status":"TOU_TARIFF_PROFILE_SAVED",
            "write_sent":False,
            "tariff_revision":revision,
            "profile":profile,
            "tracking_active":accounting is not None,
            "notice":"New rates apply prospectively; past priced intervals are not re-priced.",
        }

    hass.services.async_register(
        DOMAIN,"save_tariff_profile",save_tariff_profile,
        schema=vol.Schema({
            vol.Required("profile_json"):str,
            vol.Optional("entry_id"):str,
        }),
        supports_response=SupportsResponse.ONLY,
    )
    # Historical PV model calibration: read-only HA Recorder and archived
    # meteorological observations. No inverter writes, no YAML or extra repo.
    async def scan_forecast_history(call):
        matches=[
            e for e in hass.config_entries.async_entries(DOMAIN)
            if getattr(e,"runtime_data",None) is not None
            and (not call.data.get("entry_id") or
                 e.entry_id==call.data["entry_id"])
        ]
        if len(matches)!=1:
            raise vol.Invalid("Select exactly one SAJ H2 control entry")
        forecast=getattr(matches[0].runtime_data,"editable_forecast",None)
        if forecast is None:
            raise vol.Invalid("Editable solar forecast is not configured")
        days=call.data.get("days",180)
        return {"write_sent":False,
                "result":await forecast.async_backfill_history(days,force=True)}

    hass.services.async_register(
        DOMAIN,"scan_forecast_history",scan_forecast_history,
        schema=vol.Schema({
            vol.Optional("days",default=180):vol.In((30,90,180,365)),
            vol.Optional("entry_id"):str,
        }),
        supports_response=SupportsResponse.ONLY,
    )
    return True


class SajTOUCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, entry):
        super().__init__(
            hass, _LOGGER, name="SAJ H2 TOU readback",
            update_interval=timedelta(seconds=int(
                entry.data.get("scan_interval", DEFAULT_SCAN_INTERVAL))),
        )
        self.entry = entry
        self.last_successful_poll = None
        self.change_count = 0
        self.last_device_change = None
        self.last_changes = ()

    def _connection_details(self):
        """Use a linked SAJ Safe Monitor rather than scanning LAN devices."""
        monitors = self.hass.config_entries.async_entries("saj_h2_safe")
        source_id = self.entry.data.get("source_monitor_entry_id")
        if source_id:
            monitor = next((e for e in monitors if e.entry_id == source_id), None)
            if monitor is None or not monitor.data.get("host"):
                raise UpdateFailed("Linked SAJ Safe Monitor missing")
            return monitor.data["host"], monitor.data.get("port", 502)
        current_host = self.entry.data.get("host")
        matches = [e for e in monitors if e.data.get("host") == current_host]
        if len(matches) == 1:
            return matches[0].data["host"], matches[0].data.get("port", 502)
        return current_host, self.entry.data.get("port", 502)

    async def _async_update_data(self):
        host, port = self._connection_details()
        client = AsyncModbusTcpClient(
            host,
            port=port,
            timeout=5, retries=0,
        )
        try:
            if not await client.connect():
                raise UpdateFailed("Modbus TCP connection unavailable")
            method = client.read_holding_registers
            params = inspect.signature(method).parameters
            unit_key = "device_id" if "device_id" in params else "slave"

            async def read(address, count):
                reply = await method(address=address, count=count,
                                     **{unit_key: UNIT_ID})
                if reply is None or reply.isError() or len(reply.registers) != count:
                    raise UpdateFailed(f"Invalid read-only response at {address:#06x}")
                return reply.registers

            # The SAJ app can save an individual slot while this client is
            # polling. Verify the ENTIRE schedule block twice, not just masks.
            # Otherwise an old slot could be paired with a new mode/mask.
            async def complete_snapshot():
                return (
                    await read(CHARGE_START, CHARGE_COUNT),
                    await read(DISCHARGE_START, DISCHARGE_COUNT),
                    (await read(MODE_ADDR, 1))[0],
                    (await read(FALLBACK_ADDR, 1))[0],
                )

            first = await complete_snapshot()
            second = await complete_snapshot()
            if first != second:
                raise UpdateFailed(
                    "TOU settings changed during readback; retry next poll")

            config = decode_config(*first)
            previous = self.data
            checked_at = datetime.now(timezone.utc)
            if (previous is not None and
                    active_signature(config) != active_signature(previous["config"])):
                self.change_count += 1
                self.last_device_change = checked_at
                self.last_changes = describe_changes(previous["config"], config)
            self.last_successful_poll = checked_at
            return {
                "config": config,
                "timestamp": checked_at,
                "change_count": self.change_count,
                "last_device_change": self.last_device_change,
                "last_changes": self.last_changes,
            }
        except InvalidTOUData as exc:
            raise UpdateFailed(f"Invalid TOU settings readback: {exc}") from exc
        except UpdateFailed:
            raise
        except Exception as exc:
            raise UpdateFailed(f"TOU read-only polling failed: {type(exc).__name__}: {exc}") from exc
        finally:
            client.close()


async def async_setup_entry(hass: HomeAssistant, entry):
    coordinator = SajTOUCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    # Safe local journal is attached to this inverter only. It cannot
    # authorize writes; interrupted sessions are flagged on startup.
    from .vpp_safety_supervisor import VPPSafetySupervisor, ACTIVE, parse_utc
    from homeassistant.components.persistent_notification import (
        async_create as async_create_notification,
    )
    supervisor=VPPSafetySupervisor(hass,entry)
    await supervisor.load()
    coordinator.vpp_supervisor=supervisor
    if supervisor.record["status"] in ("review_required","rehearsal_interrupted"):
        async_create_notification(
            hass,
            "SAJ VPP safety rehearsal needs review. No inverter writes were "
            "issued by the rehearsal. Open SAJ H2 Control → Control → "
            "VPP quick actions, verify the saved TOU baseline and "
            "acknowledge only after inspection. "
            +str(supervisor.record.get("last_error") or ""),
            title="SAJ H2 VPP supervisor — review required",
            notification_id="saj_h2_vpp_review_"+entry.entry_id,
        )
    entry.runtime_data = coordinator
    # Forecast is an independent read-only weather fetch, never required for
    # inverter setup. Failure must not block existing TOU controls.
    from .forecast import SajEditableForecast
    forecast = SajEditableForecast(hass, entry)
    coordinator.editable_forecast = forecast
    # Attach to a separately configured read-only monitor without changing
    # its files, IDs, config or polling. The controller still runs if missing.
    from .energy_finance import SajEnergyAccounting
    safe_entries=hass.config_entries.async_entries("saj_h2_safe")
    source_id=entry.data.get("source_monitor_entry_id")
    host=entry.data.get("host")
    selected_monitor=next((m for m in safe_entries if
        (m.entry_id==source_id or m.data.get("host")==host)
        and getattr(m,"runtime_data",None) is not None),None)
    if selected_monitor is not None:
        safe_coordinator=selected_monitor.runtime_data
        forecast._live_monitor=safe_coordinator
        accounting=SajEnergyAccounting(hass,entry,safe_coordinator)
        await accounting.async_initialize()
        coordinator.energy_accounting=accounting
        entry.async_on_unload(safe_coordinator.async_add_listener(
            accounting.on_monitor_update))
        # Forecast learning also samples existing read-only PV data, not Modbus.
        entry.async_on_unload(safe_coordinator.async_add_listener(
            forecast.on_live_update))
        _LOGGER.info("Attached read-only cost and energy sensors to existing SAJ monitor")
    else:
        _LOGGER.info("Safe Monitor not yet loaded; TOU controls and forecast remain available")
    try:
        await forecast.async_load_learning()
    except Exception as exc:
        _LOGGER.warning("Could not load solar forecast learning: %s", exc)
    try:
        await forecast.async_refresh()
    except Exception as exc:
        _LOGGER.warning("Optional solar forecast unavailable: %s", exc)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    from .frontend_setup import async_ensure_dashboard
    await async_ensure_dashboard(hass)
    # A light, bounded background scan on first setup and roughly weekly
    # thereafter. The forecast model stays usable if Recorder, HA stats or
    # archived weather is unavailable. Explicit user rescan is also supported.
    from homeassistant.helpers.event import async_track_time_interval
    async def scheduled_learning():
        await forecast.async_backfill_history(days=180)
    hass.async_create_task(scheduled_learning())
    def weekly_learning(_now):
        hass.async_create_task(scheduled_learning())
    entry.async_on_unload(async_track_time_interval(
        hass,weekly_learning,timedelta(days=7)))

    async def vpp_watchdog_tick():
        if supervisor.record["status"] not in ACTIVE:
            return
        now=datetime.now(timezone.utc)
        end=parse_utc(supervisor.record["ends_utc"])
        snapshot=None
        if now>=end:
            # At the end of the rehearsal compare ALL device raw words,
            # under the same lock as live manual commands. Never auto-restore.
            lock=hass.data.get(DOMAIN,{}).get("pilot_lock")
            if lock is not None:
                async with lock:
                    from .schedule_transaction import read_full
                    host,port=coordinator._connection_details()
                    client=AsyncModbusTcpClient(
                        host,port=int(port),timeout=5,retries=0)
                    try:
                        if await client.connect():
                            snapshot=await read_full(client)
                    except Exception as exc:
                        _LOGGER.warning(
                            "VPP no-write baseline verification unavailable: %s",exc)
                    finally:
                        client.close()
        try:
            report=await supervisor.tick(snapshot=snapshot)
            if report["status"]=="review_required":
                async_create_notification(
                    hass,
                    "VPP rehearsal ended but the saved inverter schedule could "
                    "not be verified unchanged. No VPP inverter writes were sent; "
                    "inspect elekeeper, then use Verify baseline in Control.",
                    title="SAJ VPP — schedule review required",
                    notification_id="saj_h2_vpp_review_"+entry.entry_id,
                )
        except Exception:
            _LOGGER.exception("VPP safety watchdog tick failed; no writes attempted")

    def scheduled_vpp_tick(_now):
        hass.async_create_task(vpp_watchdog_tick())
    entry.async_on_unload(async_track_time_interval(
        hass,scheduled_vpp_tick,timedelta(seconds=20)))
    return True


async def async_unload_entry(hass: HomeAssistant, entry):
    accounting=getattr(getattr(entry,"runtime_data",None),"energy_accounting",None)
    if accounting is not None:
        try:
            await accounting.async_save()
        except Exception:
            _LOGGER.exception("Could not flush energy accounting state")
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
