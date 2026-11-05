"""Repository integrity and UI/packaging regressions (no HA or inverter I/O)."""
import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
CUSTOM = ROOT / "custom_components" / "saj_h2_control_enhanced"
JS = CUSTOM / "frontend" / "saj-tou-dynamic-card.js"


class PackageAndUI(unittest.TestCase):
    def test_hacs_marketplace_one_integration_and_config_flow(self):
        hacs = json.loads((ROOT / "hacs.json").read_text())
        manifest = json.loads((CUSTOM / "manifest.json").read_text())
        self.assertEqual(hacs["name"], "SAJ H2 Control Enhanced")
        self.assertEqual(manifest["domain"], "saj_h2_control_enhanced")
        self.assertTrue(manifest["config_flow"])
        self.assertEqual(
            [p.name for p in (ROOT / "custom_components").iterdir() if p.is_dir()],
            ["saj_h2_control_enhanced"],
        )
        for name in ("__init__.py", "config_flow.py", "frontend_setup.py",
                     "sensor.py", "schedule_transaction.py",
                     "supervised_write.py", "supervised_fallback.py"):
            self.assertTrue((CUSTOM / name).is_file(), name)
        self.assertTrue(JS.is_file())

    def test_versioned_js_url_matches_manifest(self):
        manifest = json.loads((CUSTOM / "manifest.json").read_text())
        version = manifest["version"]
        self.assertRegex(version, r"^0\.\d+\.\d+$")
        tag = "v" + "".join(version.split("."))
        frontend = (CUSTOM / "frontend_setup.py").read_text()
        self.assertIn(f"/saj-h2-tou/{tag}/saj-tou-dynamic-card.js", frontend)

    def test_install_and_dashboard_are_all_ui_no_yaml(self):
        frontend = (CUSTOM / "frontend_setup.py").read_text()
        init = (CUSTOM / "__init__.py").read_text()
        script = ROOT / "scripts" / "install.sh"
        self.assertTrue(script.is_file())
        self.assertTrue((ROOT / "docs" / "INSTALLATION.md").is_file())
        self.assertIn("async_register_static_paths", frontend)
        self.assertIn("add_extra_js_url", frontend)
        self.assertIn("async def async_ensure_dashboard", frontend)
        self.assertIn('\"title\": \"SAJ H2 Control\"', frontend)
        self.assertIn('\"cards\": [{\"type\": \"custom:saj-tou-dynamic-card\"}]', frontend)
        self.assertIn("await async_ensure_dashboard(hass)", init)
        self.assertIn("async_step_user", (CUSTOM / "config_flow.py").read_text())
        self.assertIn("No configuration.yaml", script.read_text())
        bundled = ROOT / "bundled_components" / "saj_h2_safe"
        self.assertTrue(bundled.is_dir())
        for name in ("__init__.py", "config_flow.py", "const.py", "manifest.json",
                     "sensor.py", "solar_forecast.py", "solar_model.py"):
            self.assertTrue((bundled / name).is_file(), name)
        source = script.read_text()
        self.assertIn("bundled_components/saj_h2_safe", source)
        self.assertIn("Existing SAJ H2 Safe Monitor detected", source)
        self.assertNotIn("saj-h2-safe-enhanced/archive", source)

    def test_clean_visual_statuses_and_compact_schedule_actions(self):
        card = JS.read_text()
        self.assertIn('"controlSummary"', card)
        self.assertIn('"summaryLabel","Operating"', card)
        self.assertIn('"summaryLabel","Outside TOU"', card)
        self.assertIn('e.operating_mode?.state||"Unavailable"', card)
        self.assertIn('e.outside_schedule?.state||"Unavailable"', card)
        self.assertNotIn('"Live mode · Outside TOU"', card)
        self.assertNotIn('el("span","deviceState","Device: "', card)
        self.assertIn('"addSchedule","+ Add "+direction', card)
        self.assertIn('"scheduleFootnote"', card)
        self.assertNotIn("Edit times, weekdays (Mon–Sun) and power, then Save", card)
        self.assertIn('"Save schedule changes to inverter"', card)
        self.assertIn('"● Unsaved changes"', card)
        self.assertIn("this._saveSchedules(group)", card)

    def test_inverter_safety_behavior_is_not_presentation_only(self):
        frontend = JS.read_text()
        self.assertIn("if(target===0 && !window.confirm(", frontend)
        self.assertIn('"supervised_outside_tou_fallback"', frontend)
        self.assertIn('"plan_schedules"', frontend)
        self.assertIn('"apply_schedules"', frontend)
        self.assertIn('"preview_mode_change"', frontend)
        self.assertIn("this._refreshBusy", frontend)

    def test_periodic_callbacks_are_asyncio_safe(self):
        init = (CUSTOM / "__init__.py").read_text()
        self.assertIn("async def weekly_learning(_now):", init)
        self.assertIn("await scheduled_learning()", init)
        self.assertIn("async def scheduled_vpp_tick(_now):", init)
        self.assertIn("await vpp_watchdog_tick()", init)
        self.assertNotIn("hass.async_create_task(vpp_watchdog_tick())", init)


if __name__ == "__main__":
    unittest.main()
