"""Register a dynamic read-only card and an independent SAJ TOU dashboard.

Safe-by-default: never modify an existing dashboard, never touch SAJ Energy.
The card uses actual Home Assistant entity registry IDs and state attributes,
not assumed sensor names. All draft inputs are frontend-only.
"""
from pathlib import Path
import logging

from homeassistant.components.http import StaticPathConfig

_LOGGER = logging.getLogger(__name__)
CARD_URL = "/saj-h2-tou/v024/saj-tou-dynamic-card.js"
CARD_PATH = "/saj-h2-tou/v024/saj-tou-dynamic-card.js"
DASHBOARD_PATH = "saj-tou-control"


async def async_register_frontend(hass):
    """Serve card via integration path; no manual /config/www copy."""
    try:
        path = Path(__file__).parent / "frontend" / "saj-tou-dynamic-card.js"
        await hass.http.async_register_static_paths(
            [StaticPathConfig(CARD_PATH, str(path), False)]
        )
        # Home Assistant loads this URL as a global JS resource. The custom
        # card itself is inert until a dashboard places it.
        from homeassistant.components.frontend import add_extra_js_url
        add_extra_js_url(hass, CARD_URL)
        _LOGGER.info("Registered dynamic TOU card at %s", CARD_URL)
    except Exception:
        _LOGGER.exception(
            "Automatic TOU card registration unavailable. See manual resource instructions."
        )


async def async_ensure_dashboard(hass):
    """Create a separate storage dashboard ONLY if one does not exist.

    Protects user-created dashboards. No in-place dashboard edits or deletion.
    If a HA release changes internal collection APIs, log error and allow a
    manual one-card dashboard instead; do not fail inverter monitoring.
    """
    try:
        from homeassistant.components import frontend
        from homeassistant.components.lovelace import LOVELACE_DATA
        from homeassistant.components.lovelace.dashboard import (
            DashboardsCollection, LovelaceStorage
        )
        from homeassistant.components.lovelace.const import MODE_STORAGE
        lovelace = hass.data.get(LOVELACE_DATA)
        if lovelace is None or DASHBOARD_PATH in lovelace.dashboards:
            return
        collection = DashboardsCollection(hass)
        await collection.async_load()
        if any(item.get("url_path") == DASHBOARD_PATH
               for item in collection.async_items()):
            return
        record = await collection.async_create_item({
            "url_path": DASHBOARD_PATH,
            "title": "SAJ TOU Control",
            "icon": "mdi:battery-clock",
            "show_in_sidebar": True,
        })
        board = LovelaceStorage(hass, record)
        lovelace.dashboards[DASHBOARD_PATH] = board
        await board.async_save({
            "title": "SAJ TOU Control",
            "views": [{
                "title": "Time of Use",
                "path": "tou",
                "icon": "mdi:clock-outline",
                "type": "panel",
                "cards": [{"type": "custom:saj-tou-dynamic-card"}],
            }],
        })
        frontend.async_register_built_in_panel(
            hass, "lovelace", frontend_url_path=DASHBOARD_PATH,
            require_admin=False, show_in_sidebar=True,
            sidebar_title="SAJ TOU Control",
            sidebar_icon="mdi:battery-clock",
            config={"mode": MODE_STORAGE}, update=False,
        )
        _LOGGER.info("Created a separate dynamically updating SAJ TOU dashboard")
    except Exception:
        _LOGGER.exception(
            "Automatic SAJ TOU dashboard creation unavailable. "
            "Existing dashboards are unchanged; add custom:saj-tou-dynamic-card manually."
        )
