"""Discover existing SAJ Safe Monitor config entries without LAN scanning.

Always require a user-confirmed config flow (no surprise device creation).
Prefer the verified existing monitor's configured host/port to new IP input.
"""
import ipaddress
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT

from .const import DOMAIN, DEFAULT_PORT, DEFAULT_SCAN_INTERVAL


def monitor_choices(entries):
    """Existing safe monitoring entries are the only trusted discovery source."""
    return {
        "monitor:" + e.entry_id: e.title or "SAJ H2 Safe Monitor"
        for e in entries if e.data.get(CONF_HOST)
    }


class SAJTOUFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        safe_entries = self.hass.config_entries.async_entries("saj_h2_safe")
        choices = monitor_choices(safe_entries)
        if user_input is not None:
            source = user_input.get("source", "manual")
            if source == "manual":
                return await self.async_step_manual()
            source_id = source.removeprefix("monitor:")
            selected = next((e for e in safe_entries if e.entry_id == source_id), None)
            if selected is None or not selected.data.get(CONF_HOST):
                return self.async_show_form(step_id="user", errors={"base": "source_missing"},
                    data_schema=self._source_schema(choices))
            host = selected.data[CONF_HOST]
            port = selected.data.get(CONF_PORT, DEFAULT_PORT)
            await self.async_set_unique_id(host)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title="SAJ H2 Control Enhanced",
                data={CONF_HOST: host, CONF_PORT: port,
                      "source_monitor_entry_id": source_id,
                      "scan_interval": user_input["scan_interval"]},
            )
        if not choices:
            return await self.async_step_manual()
        return self.async_show_form(step_id="user",
                                    data_schema=self._source_schema(choices))

    def _source_schema(self, choices):
        return vol.Schema({
            vol.Required("source", default=next(iter(choices))):
                vol.In({**choices, "manual": "Manual IP address (fallback)"}),
            vol.Required("scan_interval", default=DEFAULT_SCAN_INTERVAL):
                vol.All(vol.Coerce(int), vol.Range(min=60, max=3600)),
        })

    async def async_step_manual(self, user_input=None):
        errors = {}
        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            try:
                ipaddress.ip_address(host)
            except ValueError:
                errors["base"] = "invalid_host"
            else:
                await self.async_set_unique_id(host)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title="SAJ H2 Control Enhanced",
                    data={**user_input, CONF_HOST: host},
                )
        return self.async_show_form(step_id="manual", errors=errors,
            data_schema=vol.Schema({
                vol.Required(CONF_HOST): str,
                vol.Required(CONF_PORT, default=DEFAULT_PORT): vol.All(
                    vol.Coerce(int), vol.Range(min=1, max=65535)),
                vol.Required("scan_interval", default=DEFAULT_SCAN_INTERVAL):
                    vol.All(vol.Coerce(int), vol.Range(min=60, max=3600)),
            }))
