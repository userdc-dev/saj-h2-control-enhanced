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
        self.assertIn('solar:"Solar production",home:"House usage"', ui)
        self.assertIn('battery:"Battery ±",grid:"Grid ±"', ui)
        self.assertIn('"Historic Data"', ui)
        self.assertIn('plot(series.gridExport,colors.grid,true)', ui)
        self.assertIn('svg.addEventListener("pointermove"', ui)
        self.assertIn('svg.addEventListener("pointerdown"', ui)
        self.assertIn('svg.addEventListener("keydown"', ui)
        self.assertNotIn('"Live energy · history"', ui)

    def test_every_graph_has_live_inspection_and_missing_data_is_honest(self):
        ui=(CONTROL / "frontend" / "saj-tou-dynamic-card.js").read_text()
        for token in (
            "_historyChart()", "_actualProjectedChart(hourly)",
            'svg.addEventListener("pointermove"',
            'svg.addEventListener("pointerdown"',
            'svg.addEventListener("keydown"',
            '_bindForecastBar(row,dayTooltip',
            '_bindForecastBar(row,hourlyTooltip',
            '_loadForecastHistory',
            'Date.now()-this._forecastHistoryFetchedAt',
            'missingSeconds', 'actualChunks',
            '"forecastSvg"', '"forecastTooltip"',
            '"forecastHourly"',
        ):
            self.assertIn(token,ui)
        self.assertIn("Gaps in actual readings are shown as breaks",ui)

    def test_sensor_copy_guide_is_selectable_and_compact(self):
        ui=(CONTROL / "frontend" / "saj-tou-dynamic-card.js").read_text()
        for token in (
            '_copyEntityId(value,button)', 'navigator.clipboard.writeText(value)',
            'input.select()', 'field.readOnly=true',
            'field.addEventListener("click",()=>field.select())',
            'el("details","energyGuide energyGuideCompact")',
            'el("div","guideGrid")',
            'sensor?.attributes?.friendly_name',
            '["Energy charged · kWh","battery_charged_energy"]',
            '["Energy discharged · kWh","battery_discharged_energy"]',
            '"grid_import_power"', '"grid_export_power"',
            'el("details","costEditorShell")',
            'el("details","costBreakdown")',
        ):
            self.assertIn(token,ui)
        self.assertNotIn('window.open(',ui)

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
