import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from zero_os.task_executor import run_task
from zero_os.zero_ai_pressure_harness import pressure_harness_run, pressure_harness_status


class ZeroAiPressureHarnessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_ai_pressure_harness_")
        self.base = Path(self.tempdir)
        (self.base / ".zero_os").mkdir(parents=True, exist_ok=True)
        (self.base / ".zero_os" / "state.json").write_text("{}\n", encoding="utf-8")

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_pressure_harness_status_is_missing_before_first_run(self) -> None:
        status = pressure_harness_status(str(self.base))
        self.assertTrue(status["ok"])
        self.assertTrue(status["missing"])
        self.assertEqual("missing", status["status"])

    def test_pressure_harness_run_writes_artifacts_and_scorecard(self) -> None:
        out = pressure_harness_run(str(self.base))

        self.assertTrue(out["ok"])
        self.assertFalse(out["missing"])
        self.assertEqual(7, out["scenario_count"])
        self.assertEqual(0, out["failed_count"])
        self.assertGreaterEqual(out["overall_score"], 100.0)
        self.assertIn("approval_flow", out["category_scores"])
        self.assertIn("routing", out["category_scores"])
        self.assertIn("task_completion", out["category_scores"])
        self.assertTrue(Path(out["path"]).exists())
        self.assertTrue(Path(out["history_path"]).exists())
        self.assertTrue(Path(out["summary_path"]).exists())

        persisted = json.loads(Path(out["path"]).read_text(encoding="utf-8"))
        self.assertEqual(out["overall_score"], persisted["overall_score"])

    def test_pressure_harness_status_returns_latest_run(self) -> None:
        first = pressure_harness_run(str(self.base))
        status = pressure_harness_status(str(self.base))

        self.assertFalse(status["missing"])
        self.assertEqual(first["overall_score"], status["overall_score"])
        self.assertEqual(first["scenario_count"], status["scenario_count"])
        self.assertEqual(first["failed_count"], status["failed_count"])

    def test_pressure_harness_status_surfaces_planner_feedback(self) -> None:
        run_task(str(self.base), "browser status")

        status = pressure_harness_status(str(self.base))

        self.assertIn("planner_feedback", status)
        self.assertGreaterEqual(status["planner_feedback"]["history_count"], 1)
        self.assertIn("path", status["planner_feedback"])


if __name__ == "__main__":
    unittest.main()
