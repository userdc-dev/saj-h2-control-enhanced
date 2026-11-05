"""Offline resource registration tests: no HA instance or inverter calls."""
import importlib.util
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch


class ResourceStorageCollection:
    def __init__(self, items=()):
        self.loaded = False
        self.items = list(items)
        self.async_load = AsyncMock()
        self.async_create_item = AsyncMock(side_effect=self.create)
        self.async_update_item = AsyncMock(side_effect=self.update)

    def async_items(self):
        return self.items

    def create(self, data):
        self.items.append({"id": "created", "url": data["url"], "type": data["res_type"]})

    def update(self, item_id, data):
        item = next(item for item in self.items if item["id"] == item_id)
        item.update(url=data["url"], type=data["res_type"])


class FrontendSetupTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.extra_js = Mock()
        modules = {}
        for name in ("homeassistant", "homeassistant.components",
                     "homeassistant.components.http", "homeassistant.components.frontend",
                     "homeassistant.components.lovelace",
                     "homeassistant.components.lovelace.resources"):
            modules[name] = ModuleType(name)
        modules["homeassistant.components.http"].StaticPathConfig = lambda *args: args
        modules["homeassistant.components.frontend"].add_extra_js_url = self.extra_js
        modules["homeassistant.components.lovelace"].LOVELACE_DATA = "lovelace"
        modules["homeassistant.components.lovelace.resources"].ResourceStorageCollection = ResourceStorageCollection
        self.modules = patch.dict(sys.modules, modules)
        self.modules.start()
        self.addCleanup(self.modules.stop)
        file = Path(__file__).resolve().parents[1] / "custom_components/saj_h2_control_enhanced/frontend_setup.py"
        spec = importlib.util.spec_from_file_location("frontend_setup_under_test", file)
        self.frontend = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.frontend)

    def hass(self, resources):
        return SimpleNamespace(data={"lovelace": SimpleNamespace(resources=resources)},
                               http=SimpleNamespace(async_register_static_paths=AsyncMock()))

    async def test_first_install_and_repeated_setup_use_one_awaited_resource(self):
        resources = ResourceStorageCollection()
        hass = self.hass(resources)
        await self.frontend.async_register_frontend(hass)
        await self.frontend.async_register_frontend(hass)
        resources.async_load.assert_awaited_once()
        resources.async_create_item.assert_awaited_once_with(
            {"res_type": "module", "url": self.frontend.CARD_URL})
        hass.http.async_register_static_paths.assert_awaited_once()
        self.extra_js.assert_not_called()

    async def test_upgrade_only_updates_integration_resource(self):
        unrelated = {"id": "other", "url": "/local/my-card.js", "type": "module"}
        resources = ResourceStorageCollection([
            {"id": "saj", "url": "/saj-h2-tou/v0525/saj-tou-dynamic-card.js", "type": "module"},
            unrelated.copy(),
            {"id": "external", "url": "https://example.com/saj-h2-tou/v0525/saj-tou-dynamic-card.js", "type": "module"},
        ])
        hass = self.hass(resources)
        await self.frontend.async_register_card_resource(hass)
        await self.frontend.async_register_card_resource(hass)
        resources.async_update_item.assert_awaited_once_with(
            "saj", {"res_type": "module", "url": self.frontend.CARD_URL})
        resources.async_create_item.assert_not_called()
        self.assertEqual(resources.items[1], unrelated)
        self.assertTrue(resources.items[2]["url"].startswith("https://example.com/"))

    async def test_yaml_resources_are_not_modified(self):
        resources = SimpleNamespace(async_items=Mock(return_value=[]))
        hass = self.hass(resources)
        await self.frontend.async_register_frontend(hass)
        resources.async_items.assert_not_called()
        self.extra_js.assert_called_once_with(hass, self.frontend.CARD_URL)

    async def test_registration_failure_does_not_break_integration_setup(self):
        hass = self.hass(ResourceStorageCollection())
        hass.http.async_register_static_paths.side_effect = RuntimeError("HTTP unavailable")
        await self.frontend.async_register_frontend(hass)
        self.assertNotIn(self.frontend._REGISTERED, hass.data)


if __name__ == "__main__":
    unittest.main()
