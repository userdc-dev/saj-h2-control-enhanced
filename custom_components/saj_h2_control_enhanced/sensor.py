"""Expose actual inverter TOU settings as read-only HA sensor entities."""
from homeassistant.components.sensor import SensorEntity
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


async def async_setup_entry(hass, entry, async_add_entities):
    entities = [SajTOUSensor(entry.runtime_data, key) for key in DETAILS]
    forecast = getattr(entry.runtime_data, "editable_forecast", None)
    if forecast is not None:
        entities.append(SajEditableForecastSensor(forecast))
    async_add_entities(entities)
