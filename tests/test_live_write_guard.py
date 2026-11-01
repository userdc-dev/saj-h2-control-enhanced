"""Static safety checks of the only permitted hardware write implementation."""
import ast
from pathlib import Path
import unittest

PATH = Path("custom_components/saj_h2_control_enhanced/supervised_write.py")


class GuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = PATH.read_text()
        cls.tree = ast.parse(cls.source)

    def test_exactly_one_write_call(self):
        calls = [
            n for n in ast.walk(self.tree)
            if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Name) and n.func.id == "writer"
        ]
        self.assertEqual(len(calls), 1)

    def test_write_is_mode_register_and_one(self):
        calls = [
            n for n in ast.walk(self.tree)
            if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Name) and n.func.id == "writer"
        ]
        kws = {k.arg: k.value for k in calls[0].keywords}
        self.assertEqual(kws["address"].id, "MODE_ADDR")
        self.assertIsInstance(kws["value"], ast.Constant)
        self.assertEqual(kws["value"].value, 1)

    def test_only_one_register_writer_binding(self):
        attrs = [
            n.attr for n in ast.walk(self.tree)
            if isinstance(n, ast.Attribute) and n.attr.startswith("write_")
        ]
        self.assertEqual(attrs, ["write_register"])

    def test_no_write_loop_or_automatic_rollback(self):
        self.assertNotIn("await writer(", self.source.split("for check in range")[1])
        self.assertNotIn("write_registers", self.source)
        self.assertNotIn("rollback", self.source.split("async def run_supervised_tou_test")[1].split('"""')[1])

    def test_requires_confirmation_and_expected_mode(self):
        self.assertIn("confirmed_phrase != CONFIRM_PHRASE", self.source)
        self.assertIn("expected_mode != 0", self.source)
        self.assertIn("if second != before:", self.source)
        self.assertIn("after.charge_slots", self.source)
        self.assertIn("after.discharge_slots", self.source)


if __name__ == "__main__":
    unittest.main()
