"""Configuration; no write or control modes are offered."""
import ipaddress
import voluptuous as vol
from homeassistant import config_entries
from .const import DOMAIN, DEFAULT_PORT, DEFAULT_SCAN_INTERVAL

class SajSafeFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            host = user_input["host"].strip()
            try:
                ipaddress.ip_address(host)
            except ValueError:
                errors["base"] = "invalid_host"
            else:
                await self.async_set_unique_id(host)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"SAJ H2 Safe ({host})",
                    data={**user_input, "host": host}
                )
        schema = vol.Schema({
            vol.Required("host"): str,
            vol.Required("port", default=DEFAULT_PORT):
                vol.All(vol.Coerce(int), vol.Range(min=1, max=65535)),
            vol.Required("scan_interval", default=DEFAULT_SCAN_INTERVAL):
                vol.All(vol.Coerce(int), vol.Range(min=30, max=3600)),
        })
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)
