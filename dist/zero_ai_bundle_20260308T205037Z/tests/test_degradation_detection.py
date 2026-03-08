import json
import shutil
import tempfile
import unittest
from pathlib import Path

from ai_from_scratch.degradation_detection import run_degradation_detection


class DegradationDetectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_degradation_")
        self.base = Path(self.tempdir)
        self.runtime = self.base / ".zero_os" / "runtime"
        self.runtime.mkdir(parents=True, exist_ok=True)
        (self.runtime / "zero_ai_tasks.txt").write_text("", encoding="utf-8")
        (self.runtime / "zero_ai_output.txt").write_text("", encoding="utf-8")
        (self.runtime / "self_monitor_report.json").write_text(
            json.dumps({"summary": {"avg_confidence_recent": 1.0, "recent_rejections": 0, "env_unknown_recent": 0, "rejection_streak": 0}}),
            encoding="utf-8",
        )
        (self.runtime / "signal_reliability.json").write_text(
            json.dumps({"history": [], "current": {"logic": 1.0, "environment": 1.0, "survival": 1.0}}),
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_healthy_state_reports_no_degradation(self) -> None:
        out = run_degradation_detection(str(self.base))
        self.assertTrue(out["ok"])
        self.assertFalse(out["degraded"])
        self.assertIn("indicators", out)

    def test_degraded_state_triggers_actions(self) -> None:
        (self.runtime / "self_monitor_report.json").write_text(
            json.dumps({"summary": {"avg_confidence_recent": 0.4, "recent_rejections": 8, "env_unknown_recent": 6, "rejection_streak": 5}}),
            encoding="utf-8",
        )
        (self.runtime / "signal_reliability.json").write_text(
            json.dumps({"history": [], "current": {"logic": 0.5, "environment": 0.4, "survival": 0.52}}),
            encoding="utf-8",
        )
        out = run_degradation_detection(str(self.base))
        self.assertTrue(out["degraded"])
        self.assertEqual("adaptive", out["actions"]["set_profile"])
        self.assertEqual("exploration", out["actions"]["set_mode"])


if __name__ == "__main__":
    unittest.main()

