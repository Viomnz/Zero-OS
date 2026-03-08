import shutil
import tempfile
import unittest
from pathlib import Path

from ai_from_scratch.long_horizon_strategy import update_long_horizon_strategy


class LongHorizonStrategyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_horizon_")
        self.base = Path(self.tempdir)

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_strategy_update_written(self) -> None:
        out = update_long_horizon_strategy(
            str(self.base),
            "optimize security and performance",
            {"reasoning_parameters": {"priority_mode": "normal"}},
            {"learning_score": 0.84, "signal_type": "positive"},
            {"enter_safe_state": False},
        )
        self.assertTrue(out["ok"])
        self.assertIn("next_review_utc", out)
        path = self.base / ".zero_os" / "runtime" / "long_horizon_strategy.json"
        self.assertTrue(path.exists())

    def test_high_risk_counter_increments(self) -> None:
        out = update_long_horizon_strategy(
            str(self.base),
            "critical unstable path",
            {"reasoning_parameters": {"priority_mode": "normal"}},
            {"learning_score": 0.2, "signal_type": "negative"},
            {"enter_safe_state": True},
        )
        self.assertGreaterEqual(out["risk_drift"], 0.6)
        self.assertGreaterEqual(out["stats"]["high_risk_updates"], 1)


if __name__ == "__main__":
    unittest.main()
