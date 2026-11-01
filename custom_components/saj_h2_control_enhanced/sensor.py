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
            return "Readback OK (not verified with eLEKeeper live)"

    @property
    def extra_state_attributes(self):
        if not self.coordinator.data or not self.coordinator.last_update_success:
            return None
        data = self.coordinator.data
        config = data["config"]
        base = {
            "last_verified_read": data["timestamp"].isoformat(),
            "external_changes_detected_since_start": data["change_count"],
            "read_only": True,
            "write_controls_available": False,
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
            base["power_scale_status"] = "Charge watts conversion unverified"
        elif self.key == "discharge_schedules":
            base["schedules"] = config.summary("discharge")
            base["power_scale_status"] = "Discharge display W = raw × 99 verified for this installation"
        elif self.key == "sync_status":
            base["note"] = "Modbus confirms saved settings; actual scheduled execution and cloud app refresh may lag"
        return base


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([
        SajTOUSensor(entry.runtime_data, key) for key in DETAILS
    ])
