"""Expose actual inverter TOU settings as read-only HA sensor entities."""
from homeassistant.components.sensor import (
    SensorEntity, SensorDeviceClass, SensorStateClass,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN

DETAILS = {
    "operating_mode": "Operating mode",
    "outside_schedule": "Outside schedule behaviour",
    "charge_count": "Enabled charge schedules",
    "discharge_count": "Enabled discharge schedules",
    "charge_schedules": "Charge schedules",
    "discharge_schedules": "Discharge schedules",
    "sync_status": "TOU device sync",
}


class SajTOUSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, coordinator, key):
        super().__init__(coordinator)
        self.key = key
        self._attr_name = DETAILS[key]
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{key}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, coordinator.entry.entry_id)},
            "name": "SAJ H2 TOU Readback",
            "manufacturer": "SAJ",
            "model": "H2 · separate read-only settings",
        }

    @property
    def native_value(self):
        if not self.coordinator.last_update_success or not self.coordinator.data:
            return None
        d = self.coordinator.data
        c = d["config"]
        if self.key == "operating_mode":
            return c.mode_text
        if self.key == "outside_schedule":
            return c.fallback_text
        if self.key == "charge_count":
            return sum(s.enabled for s in c.charge_slots)
        if self.key == "discharge_count":
            return sum(s.enabled for s in c.discharge_slots)
        if self.key == "charge_schedules":
            return f"{sum(s.enabled for s in c.charge_slots)} configured"
        if self.key == "discharge_schedules":
            return f"{sum(s.enabled for s in c.discharge_slots)} configured"
        if self.key == "sync_status":
            return "Readback OK (not verified with elekeeper live)"

    @property
    def extra_state_attributes(self):
        if not self.coordinator.data or not self.coordinator.last_update_success:
            return {"saj_tou_role": self.key,
                    "saj_tou_entry_id": self.coordinator.entry.entry_id,
                    "read_only": True, "write_controls_available": False}
        data = self.coordinator.data
        config = data["config"]
        base = {
            "last_verified_read": data["timestamp"].isoformat(),
            "last_device_change": (data["last_device_change"].isoformat()
                                   if data["last_device_change"] else None),
            "last_changes": list(data["last_changes"]),
            "external_changes_detected_since_start": data["change_count"],
            "read_only": True,
            "write_controls_available": True,
            "saj_tou_role": self.key,
            "saj_tou_entry_id": self.coordinator.entry.entry_id,
        }
        if self.key == "operating_mode":
            base.update({
                "raw_mode_code": config.mode,
                "device_source": "Modbus holding register 0x3647",
            })
        elif self.key == "outside_schedule":
            base["raw_fallback_code"] = config.fallback
        elif self.key == "charge_count":
            base["slot_enable_mask"] = config.charge_mask
        elif self.key == "discharge_count":
            base["slot_enable_mask"] = config.discharge_mask
        elif self.key == "charge_schedules":
            base["schedules"] = config.summary("charge")
            base["power_scale_status"] = "Charging display W = raw × 99, paired app values confirmed at raw 50 and 70; other values modeled"
        elif self.key == "discharge_schedules":
            base["schedules"] = config.summary("discharge")
            base["power_scale_status"] = "Discharge display W = raw × 99 verified for this installation"
        elif self.key == "sync_status":
            base["note"] = ("Device register readback succeeded. This is not proof "
                            "of elekeeper cloud refresh or schedule execution.")
        return base


class SajEditableForecastSensor(CoordinatorEntity, SensorEntity):
    """Read-only forecast state and metadata exposed to the dashboard."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_name = "Editable solar forecast"
    _attr_native_unit_of_measurement = "kWh"
    _attr_icon = "mdi:weather-sunny"

    def __init__(self, forecast):
        super().__init__(forecast)
        self._attr_unique_id = f"{forecast.entry.entry_id}_editable_forecast"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, forecast.entry.entry_id)},
            "name": "SAJ H2 TOU Readback",
            "manufacturer": "SAJ",
            "model": "H2 · separate read-only settings",
        }

    @property
    def native_value(self):
        if not self.coordinator.last_update_success:
            return None
        return (self.coordinator.data or {}).get("today")

    @property
    def extra_state_attributes(self):
        from .forecast import settings_for
        data = self.coordinator.data or {}
        return {
            "saj_tou_role": "editable_forecast",
            "saj_tou_entry_id": self.coordinator.entry.entry_id,
            "read_only": True,
            **data,
            "settings": data.get("settings", settings_for(self.coordinator.entry)),
        }


# These stable, human-readable read-only aliases are intended for the built-in
# Home Assistant Energy configuration. Grid kWh is explicitly estimated from
# signed power samples; NEVER imply the raw SAJ feed-in/sell registers are
# direction-verified. No duplicate Modbus connections are opened here.
ENERGY_BRIDGE = {
    "solar_production_energy": ("Solar production energy • total","solar_total","kWh","energy"),
    "solar_production_power": ("Solar production power","total_pv_power","W","power"),
    "battery_charged_energy": ("Battery energy charged • total","battery_charge_total","kWh","energy"),
    "battery_discharged_energy": ("Battery energy discharged • total","battery_discharge_total","kWh","energy"),
    "battery_state_of_charge": ("Battery state of charge","battery_soc","%","battery"),
    "battery_power": ("Battery power • signed","battery_power","W","power"),
    "home_consumption_energy": ("Home energy consumed • total","home_total","kWh","energy"),
    "home_consumption_power": ("House consumption power","home_load_power","W","power"),
    "grid_signed_power": ("Grid power • signed (import + / export −)","grid_power","W","power"),
    "grid_import_power": ("Power imported from grid • provisional","grid_import","W","power"),
    "grid_export_power": ("Power exported to grid • provisional","grid_export","W","power"),
    "grid_import_energy_estimate": ("Grid energy imported • estimated","accounting:lifetime:import_kwh","kWh","energy"),
    "grid_export_energy_estimate": ("Grid energy exported • estimated","accounting:lifetime:export_kwh","kWh","energy"),
}

class SajEnergyBridgeSensor(CoordinatorEntity, SensorEntity):
    """Expose existing monitor values with correct HA Energy statistics metadata."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, accounting, key):
        super().__init__(accounting)
        self.key = key
        name, source, unit, kind = ENERGY_BRIDGE[key]
        self.source = source
        self._attr_name = name
        self._attr_unique_id = f"{accounting.entry.entry_id}_energy_bridge_{key}"
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = {
            "energy":SensorDeviceClass.ENERGY,
            "power":SensorDeviceClass.POWER,
            "battery":SensorDeviceClass.BATTERY,
        }[kind]
        self._attr_state_class = (
            SensorStateClass.TOTAL_INCREASING if kind=="energy"
            else SensorStateClass.MEASUREMENT
        )
        self._attr_device_info = {
            "identifiers":{(DOMAIN,accounting.entry.entry_id)},
            "name":"SAJ H2 TOU Readback",
            "manufacturer":"SAJ",
            "model":"H2 · existing read-only monitor data",
        }

    @property
    def native_value(self):
        data=self.coordinator.data or {}
        if self.source.startswith("accounting:"):
            _,period,key=self.source.split(":")
            return data.get("accounting",{}).get(period,{}).get(key)
        if not self.coordinator.monitor.last_update_success:
            return None
        return data.get(self.source)

    @property
    def extra_state_attributes(self):
        estimated=self.source.startswith("accounting:")
        grid=self.key.startswith("grid_")
        return {
            "source":"Home Assistant recorded SAJ Safe Monitor data",
            "saj_energy_role":self.key,
            "read_only":True,
            "direction_unverified":grid,
            "estimated_not_billing_meter":estimated,
            "explanation":(
                "Power-integrated estimate; only monitored intervals count. "
                "Verify grid polarity before use for billing."
                if estimated else
                "Uses existing lifetime inverter counter or instantaneous power/SOC."),
        }


class SajCostEstimateSensor(CoordinatorEntity, SensorEntity):
    """UI source: signed-tariff partial-period estimated costs and coverage."""

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_name = "Estimated electricity cost today"
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_icon = "mdi:currency-usd"

    def __init__(self, accounting):
        super().__init__(accounting)
        self._attr_native_unit_of_measurement = accounting.hass.config.currency or "AUD"
        self._attr_unique_id = f"{accounting.entry.entry_id}_cost_estimate"
        self._attr_device_info = {
            "identifiers":{(DOMAIN,accounting.entry.entry_id)},
            "name":"SAJ H2 TOU Readback",
            "manufacturer":"SAJ",
            "model":"H2 · estimated electricity costs",
        }

    @property
    def native_value(self):
        payload=self.coordinator.data or {}
        pricing=payload.get("pricing",{})
        if not pricing.get("configured"):
            return None
        return (payload.get("costs",{}).get("today") or {}).get("net_cost")

    @property
    def extra_state_attributes(self):
        data=self.coordinator.data or {}
        return {
            "saj_tou_role":"cost_estimate",
            "saj_tou_entry_id":self.coordinator.entry.entry_id,
            "pricing":data.get("pricing",{}),
            "current_tariff":data.get("current_tariff"),
            "today":data.get("costs",{}).get("today"),
            "month":data.get("costs",{}).get("month"),
            "direction_unverified":True,
            "estimation_not_billing":True,
            "read_only":True,
            "note":"Signed static tariff estimate, calculated from power-integrated monitored intervals only; grid polarity not field verified."
        }


async def async_setup_entry(hass, entry, async_add_entities):
    entities = [SajTOUSensor(entry.runtime_data, key) for key in DETAILS]
    forecast = getattr(entry.runtime_data, "editable_forecast", None)
    if forecast is not None:
        entities.append(SajEditableForecastSensor(forecast))
    accounting = getattr(entry.runtime_data,"energy_accounting",None)
    if accounting is not None:
        entities.extend(SajEnergyBridgeSensor(accounting,key) for key in ENERGY_BRIDGE)
        entities.append(SajCostEstimateSensor(accounting))
    async_add_entities(entities)
