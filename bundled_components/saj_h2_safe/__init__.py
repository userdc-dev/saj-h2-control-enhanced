"""SAJ H2 Safe Enhanced — read-only Modbus poller."""
from datetime import timedelta
import asyncio
import inspect
import logging
from time import monotonic
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from pymodbus.client import AsyncModbusTcpClient
from .solar_forecast import SajSolarForecastCoordinator
from .const import (
    DEFAULT_SCAN_INTERVAL, DEFAULT_BATTERY_CAPACITY_KWH, SENSORS,
    ENERGY_KEYS, MODE_LABELS, decode, decode_energy, derived_values,
)

_LOGGER = logging.getLogger(__name__)
PLATFORMS = ["sensor"]

class SajSafeCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, entry):
        self.entry = entry
        self._lock = asyncio.Lock()
        self.failures = 0
        self._counter_cache = {}
        self._counter_updated_at = 0.0
        self._mode_cache = None
        self._mode_updated_at = 0.0
        super().__init__(
            hass, _LOGGER, name="SAJ H2 Safe Enhanced",
            update_interval=timedelta(
                # Existing installations stored a 60s interval in entry.data.
                # Live update rate is now independently set to 10s by default.
                seconds=max(5, min(60, int(entry.options.get("live_scan_interval", 10))))
            ),
        )

    async def _async_update_data(self):
        # Only read_holding_registers (Modbus function 03) is used.
        # Never auto-write, reconfigure the inverter, or publish fake zeros.
        async with self._lock:
            client = AsyncModbusTcpClient(
                self.entry.data["host"], port=self.entry.data["port"],
                timeout=5, retries=0,
            )
            try:
                if not await client.connect():
                    raise UpdateFailed("Cannot connect to SAJ inverter")
                read = client.read_holding_registers
                kw = {"device_id": 1} if "device_id" in inspect.signature(read).parameters else {"slave": 1}

                async def fetch(address, count):
                    response = await read(address=address, count=count, **kw)
                    if response is None or response.isError() or len(response.registers) != count:
                        raise ValueError(f"Modbus response invalid for {address:#06x}")
                    return response.registers

                result = {}
                # The original established three groups must succeed.
                for address, count in ((0x4069, 7), (0x4071, 9), (0x40A0, 14)):
                    words = await fetch(address, count)
                    result.update({address + n: value for n, value in enumerate(words)})

                parsed = {}
                for key, (address, _, _, factor, signed, low, high) in SENSORS.items():
                    if address is not None:
                        parsed[key] = decode(result[address], signed, factor, low, high)

                if parsed["battery_soc"] is None:
                    raise UpdateFailed("Battery SOC invalid; data discarded")

                capacity = self.entry.options.get(
                    "battery_capacity_kwh",
                    self.entry.data.get("battery_capacity_kwh", DEFAULT_BATTERY_CAPACITY_KWH),
                )
                derived_values(parsed, capacity)

                now = monotonic()
                # Slow-changing operating mode and energy counters are refreshed
                # once per minute, independent of the 10-second live readings.
                if self._mode_cache is None or now - self._mode_updated_at >= 60:
                    try:
                        code = (await fetch(0x3647, 1))[0]
                        self._mode_cache = MODE_LABELS.get(code, f"Unknown (code {code})")
                        self._mode_updated_at = now
                    except Exception as exc:
                        _LOGGER.debug("Operating mode temporarily unavailable: %s", exc)
                parsed["operating_mode"] = self._mode_cache

                if not self._counter_cache or now - self._counter_updated_at >= 60:
                    new_counters = {}
                    # An incomplete block must not replace previously good
                    # counters with zero or corrupt the live readings.
                    for start in (0x40BF, 0x40DF):
                        try:
                            words = await fetch(start, 32)
                            for key, (address, _) in ENERGY_KEYS.items():
                                if start <= address and address + 1 < start + 32:
                                    new_counters[key] = decode_energy(
                                        words[address - start], words[address - start + 1]
                                    )
                        except Exception as exc:
                            _LOGGER.debug("Energy block %04X temporarily unavailable: %s", start, exc)
                    if new_counters:
                        self._counter_cache.update(new_counters)
                        if len(new_counters) == len(ENERGY_KEYS):
                            self._counter_updated_at = now
                for key in ENERGY_KEYS:
                    parsed[key] = self._counter_cache.get(key)

                self.failures = 0
                return parsed
            except UpdateFailed:
                self.failures += 1
                raise
            except Exception as exc:
                self.failures += 1
                raise UpdateFailed(f"SAJ read failed: {type(exc).__name__}: {exc}") from exc
            finally:
                client.close()

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    coordinator = SajSafeCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    # Forecast availability never blocks the working local Modbus integration.
    forecast = SajSolarForecastCoordinator(hass, entry, coordinator)
    coordinator.forecast = forecast
    await forecast.async_load_history()
    try:
        await forecast.async_refresh()
    except Exception as exc:
        _LOGGER.warning("Solar forecast initial refresh failed (live readings still work): %s", exc)
    entry.async_on_unload(coordinator.async_add_listener(forecast.on_live_update))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
