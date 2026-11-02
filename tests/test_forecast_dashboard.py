"""Static regression checks for independent read-only forecast and UI.

No Home Assistant connection, internet weather request or inverter write.
"""
import ast
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
CONTROL = ROOT / "custom_components" / "saj_h2_control_enhanced"


class ForecastDashboardTests(unittest.TestCase):
    def test_forecast_engine_is_read_only(self):
        source = (CONTROL / "forecast.py").read_text()
        ast.parse(source)
        self.assertIn("global_tilted_irradiance", source)
        self.assertIn("DEFAULT_GROUPS", source)
        self.assertIn("DEFAULT_EFFICIENCY = 87", source)
        self.assertIn("DEFAULT_AC_LIMIT = 10.0", source)
        self.assertIn("async_get_clientsession", source)
        self.assertNotIn("write_register", source)
        self.assertNotIn("write_registers", source)
        self.assertNotIn("AsyncModbusTcpClient", source)

    def test_dashboard_has_navigation_settings_and_history(self):
        ui = (CONTROL / "frontend" / "saj-tou-dynamic-card.js").read_text()
        for token in ('_forecastPage()', '_actualProjectedChart(hourly)',
                      '_historyChart()', '_loadHistory()', '_saveForecastSettings()',
                      'history/period/', 'groups_json', 'Forecast details'):
            self.assertIn(token, ui)
        self.assertIn('this._goPage("forecast")', ui)
        self.assertIn('"Save settings & recalculate"', ui)
        self.assertIn('Solar",home:"House"', ui)
        self.assertIn('battery:"Battery",grid:"Grid",forecast:"Forecast"', ui)

    def test_forecast_service_is_separate_from_inverter_writes(self):
        source = (CONTROL / "__init__.py").read_text()
        self.assertIn('"save_forecast_settings"', source)
        self.assertIn("forecast_groups", source)
        self.assertIn("forecast_efficiency", source)
        self.assertIn("forecast_ac_limit_kw", source)
        self.assertIn('"write_sent": False', source)
        sensor = (CONTROL / "sensor.py").read_text()
        self.assertIn('SajEditableForecastSensor', sensor)
        self.assertIn('"kWh"', sensor)


if __name__ == "__main__":
    unittest.main()
