"""SAJ H2 TOU readback coordinator. Modbus function 03 ONLY.

This module has NO inverter write functions, services, buttons or switches.
An independent TCP connection is used once every 120s by default.
"""
from datetime import datetime, timedelta, timezone
import inspect
import logging

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from pymodbus.client import AsyncModbusTcpClient

from .const import DEFAULT_SCAN_INTERVAL, UNIT_ID
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
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    from .frontend_setup import async_ensure_dashboard
    await async_ensure_dashboard(hass)
    return True


async def async_unload_entry(hass: HomeAssistant, entry):
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
