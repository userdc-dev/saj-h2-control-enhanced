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
)

_LOGGER = logging.getLogger(__name__)
PLATFORMS = ("sensor",)


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

    async def _async_update_data(self):
        client = AsyncModbusTcpClient(
            self.entry.data["host"],
            port=self.entry.data["port"],
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

            # Non-atomic reads: another controller might change a schedule
            # between blocks. Re-read masks and mode at the end; fail instead
            # of publishing a mixed snapshot if those changed.
            charge = await read(CHARGE_START, CHARGE_COUNT)
            discharge = await read(DISCHARGE_START, DISCHARGE_COUNT)
            mode = (await read(MODE_ADDR, 1))[0]
            fallback = (await read(FALLBACK_ADDR, 1))[0]
            masks_again = await read(CHARGE_START, 2)
            mode_again = (await read(MODE_ADDR, 1))[0]
            fallback_again = (await read(FALLBACK_ADDR, 1))[0]
            if charge[:2] != masks_again or mode != mode_again or fallback != fallback_again:
                raise UpdateFailed("TOU settings changed during snapshot; retry next poll")

            config = decode_config(charge, discharge, mode, fallback)
            previous = self.data
            if previous is not None and config != previous["config"]:
                self.change_count += 1
            self.last_successful_poll = datetime.now(timezone.utc)
            return {"config": config, "timestamp": self.last_successful_poll,
                    "change_count": self.change_count}
        except (UpdateFailed, InvalidTOUData):
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
    return True


async def async_unload_entry(hass: HomeAssistant, entry):
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
