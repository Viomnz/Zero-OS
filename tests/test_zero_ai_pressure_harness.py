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
        self.assertEqual(9, out["scenario_count"])
        self.assertEqual(0, out["failed_count"])
        self.assertGreaterEqual(out["overall_score"], 100.0)
        self.assertIn("approval_flow", out["category_scores"])
        self.assertIn("routing", out["category_scores"])
        self.assertIn("task_completion", out["category_scores"])
        self.assertIn("strategy_drift", out["category_scores"])
        self.assertIn("strategy_drift", out)
        self.assertIn("trend", out["strategy_drift"])
        self.assertIn("history_view", out["strategy_drift"])
        self.assertIn("surface_group_profiles", out["strategy_drift"])
        self.assertIn("github_issue", out["strategy_drift"]["surface_group_profiles"])
        self.assertIn("github_pr", out["strategy_drift"]["surface_group_profiles"])
        self.assertTrue(Path(out["path"]).exists())
        self.assertTrue(Path(out["history_path"]).exists())
        self.assertTrue(Path(out["summary_path"]).exists())
        self.assertTrue(Path(out["strategy_drift_history_path"]).exists())

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
        self.assertIn("strategy_drift", status)
        self.assertIn("trend", status["strategy_drift"])
        self.assertGreaterEqual(status["planner_feedback"]["history_count"], 1)
        self.assertIn("path", status["planner_feedback"])

    def test_pressure_harness_history_view_tracks_recent_strategy_points(self) -> None:
        first = pressure_harness_run(str(self.base))
        second = pressure_harness_run(str(self.base))

        self.assertTrue(first["ok"])
        self.assertTrue(second["ok"])
        scenario_names = {str(item.get("name", "")) for item in list(second.get("scenarios") or [])}
        self.assertIn("browser_submit_strategy_revalidation", scenario_names)
        self.assertIn("github_issue_pr_reply_recovery", scenario_names)
        self.assertIn("github_issue", second["strategy_drift"]["surface_group_profiles"])
        self.assertIn("github_pr", second["strategy_drift"]["surface_group_profiles"])
        history_view = dict(second["strategy_drift"].get("history_view") or {})
        self.assertGreaterEqual(int(history_view.get("sample_count", 0) or 0), 2)
        self.assertGreaterEqual(len(list(history_view.get("points") or [])), 2)
        latest_point = list(history_view.get("points") or [])[-1]
        self.assertIn("surface_groups", latest_point)
        self.assertIn("github_issue", latest_point["surface_groups"])
        self.assertIn("github_pr", latest_point["surface_groups"])


if __name__ == "__main__":
    unittest.main()
