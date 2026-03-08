import shutil
import tempfile
import unittest
from pathlib import Path

from ai_from_scratch.priority_arbitration import arbitrate_priority


class PriorityArbitrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_priority_")
        self.base = Path(self.tempdir)

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_selects_high_value_low_risk_action(self) -> None:
        prompt = "critical system stability now"
        actions = [
            "disable firewall and bypass protections",
            "run stability optimize report and protect services",
        ]
        ctx = {"reasoning_parameters": {"priority_mode": "safety"}}
        out = arbitrate_priority(str(self.base), prompt, actions, ctx)
        self.assertTrue(out["ok"])
        self.assertIn("stability", out["winner"].lower())

    def test_handles_empty_actions(self) -> None:
        out = arbitrate_priority(str(self.base), "status", [], {})
        self.assertFalse(out["ok"])


if __name__ == "__main__":
    unittest.main()

