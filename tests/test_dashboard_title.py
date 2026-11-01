"""Offline non-destructive migration tests for Home Assistant view title."""
import importlib.util
from pathlib import Path
import unittest


FILE = Path("custom_components/saj_h2_control_enhanced/dashboard_title.py")
spec = importlib.util.spec_from_file_location("dashboard_title", FILE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def old_dashboard():
    return {
        "title": "SAJ TOU Control",
        "views": [{
            "title": "Time of Use",
            "path": "tou",
            "icon": "mdi:clock-outline",
            "type": "panel",
            "cards": [{"type": "custom:saj-tou-dynamic-card"}],
        }],
    }


class TitleMigrationTest(unittest.TestCase):
    def test_updates_only_view_title_and_preserves_original(self):
        old = old_dashboard()
        updated = module.migrate_generated_view_title(old)
        self.assertEqual(updated["views"][0]["title"], "SAJ H2 Control")
        self.assertEqual(updated["title"], "SAJ TOU Control")
        self.assertEqual(updated["views"][0]["path"], "tou")
        self.assertEqual(updated["views"][0]["icon"], "mdi:clock-outline")
        self.assertEqual(updated["views"][0]["cards"], old["views"][0]["cards"])
        self.assertEqual(old["views"][0]["title"], "Time of Use")

    def test_never_replace_user_modified_or_other_dashboards(self):
        edits = (
            lambda x: x.update(title="My solar dashboard"),
            lambda x: x["views"][0].update(title="My preferred view title"),
            lambda x: x["views"][0].update(type="sections"),
            lambda x: x["views"][0].update(cards=[{"type":"entities","entities":[]}]),
            lambda x: x["views"].append({"title":"Second","cards":[]}),
            lambda x: x["views"][0].update(path="some-other-view"),
        )
        for edit in edits:
            config = old_dashboard()
            edit(config)
            with self.subTest(config=config):
                self.assertIsNone(module.migrate_generated_view_title(config))

    def test_migration_is_idempotent(self):
        updated = module.migrate_generated_view_title(old_dashboard())
        self.assertIsNone(module.migrate_generated_view_title(updated))

    def test_malformed_configs_are_skipped(self):
        for data in (None, [], {}, {"title":"SAJ TOU Control"}, {"views":None}):
            with self.subTest(data=data):
                self.assertIsNone(module.migrate_generated_view_title(data))


if __name__ == "__main__":
    unittest.main()
