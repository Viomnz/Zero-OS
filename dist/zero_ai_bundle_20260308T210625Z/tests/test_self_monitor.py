import shutil
import tempfile
import unittest
from pathlib import Path

from ai_from_scratch.self_monitor import update_self_monitor


class SelfMonitorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_monitor_")
        self.base = Path(self.tempdir)

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_detects_rejection_streak_action(self) -> None:
        trace = [
            {
                "combined_confidence": 0.2,
                "critics": {
                    "logic": {"confidence": 0.0},
                    "environment": {"status": "fail", "confidence": 0.0},
                    "survival": {"confidence": 0.2},
                },
            }
        ]
        last = None
        for _ in range(4):
            last = update_self_monitor(str(self.base), False, trace, "balanced", "stability", 1)
        self.assertTrue(last["actions"]["trigger_new_model_generation"])

    def test_switches_mode_when_env_unknown_repeats(self) -> None:
        trace = [
            {
                "combined_confidence": 0.5,
                "critics": {
                    "logic": {"confidence": 1.0},
                    "environment": {"status": "unknown", "confidence": 0.2},
                    "survival": {"confidence": 1.0},
                },
            }
        ]
        out = None
        for _ in range(6):
            out = update_self_monitor(str(self.base), False, trace, "balanced", "stability", 1)
        self.assertEqual("exploration", out["actions"]["set_mode"])


if __name__ == "__main__":
    unittest.main()
