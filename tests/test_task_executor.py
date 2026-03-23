import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from zero_os.task_executor import _execute_plan, _execute_with_replan


class TaskExecutorReplanTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_task_executor_")
        self.base = Path(self.tempdir)
        (self.base / ".zero_os").mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_execute_with_replan_does_not_reroute_after_autonomy_gate_stop(self) -> None:
        plan = {"branch": {"id": "primary"}, "steps": [{"kind": "self_repair", "target": "runtime"}]}
        selection = {
            "discarded_branches": [
                {
                    "decision": "allow",
                    "plan": {"branch": {"id": "minimal_safe"}, "steps": [{"kind": "observe", "target": "status"}]},
                }
            ]
        }
        initial_out = {
            "ok": False,
            "results": [{"ok": False, "kind": "self_repair", "reason": "autonomy_gate"}],
            "contradiction_gate": {"decision": "allow", "contradiction_count": 0},
        }

        with patch("zero_os.task_executor._execute_plan", return_value=initial_out) as mock_execute:
            out = _execute_with_replan(str(self.base), "self repair runtime", plan, selection)

        self.assertEqual(1, mock_execute.call_count)
        self.assertFalse(out["ok"])
        self.assertFalse(out["replan"]["attempted"])
        self.assertEqual("", out["replan"]["trigger"])

    def test_execute_plan_runs_conditional_fallback_after_failure(self) -> None:
        plan = {
            "intent": {"intent": "web"},
            "steps": [
                {"kind": "browser_open", "target": "https://example.com", "decomposition_subgoal_id": "subgoal_0"},
                {
                    "kind": "browser_dom_inspect",
                    "target": "https://example.com",
                    "decomposition_subgoal_id": "subgoal_1",
                    "decomposition_depends_on": ["subgoal_0"],
                    "conditional_execution_mode": "on_failure",
                    "condition_trigger_text": "open",
                    "condition_trigger_hints": ["open"],
                },
            ],
        }

        def fake_execute_step(_cwd: str, step: dict, *, run_id: str = "", plan_context=None) -> dict:
            if step["kind"] == "browser_open":
                return {"ok": False, "kind": "browser_open", "reason": "network_unreachable"}
            return {"ok": True, "kind": step["kind"], "result": {"ok": True}}

        with patch("zero_os.task_executor.execute_step", side_effect=fake_execute_step), patch(
            "zero_os.task_executor.review_run",
            return_value={"decision": "allow", "contradiction_count": 0},
        ):
            out = _execute_plan(str(self.base), "open https://example.com and if open fails inspect page https://example.com", plan, run_id="run-1")

        self.assertTrue(out["ok"])
        self.assertEqual("browser_open", out["results"][0]["kind"])
        self.assertTrue(out["results"][0]["handled_by_fallback"])
        self.assertEqual("browser_dom_inspect", out["results"][1]["kind"])
        self.assertEqual("browser_open", out["results"][1]["conditional_triggered_by"])

    def test_execute_plan_runs_success_condition_followup_after_verification(self) -> None:
        plan = {
            "intent": {"intent": "web"},
            "steps": [
                {"kind": "web_verify", "target": "https://example.com", "decomposition_subgoal_id": "subgoal_0"},
                {
                    "kind": "browser_open",
                    "target": "https://example.com",
                    "decomposition_subgoal_id": "subgoal_1",
                    "decomposition_depends_on": ["subgoal_0"],
                    "conditional_execution_mode": "on_verified",
                    "condition_trigger_text": "inspect page https://example.com",
                    "condition_trigger_hints": ["inspect"],
                },
            ],
        }

        def fake_execute_step(_cwd: str, step: dict, *, run_id: str = "", plan_context=None) -> dict:
            if step["kind"] == "web_verify":
                return {"ok": True, "kind": "web_verify", "result": {"verified": True}}
            return {"ok": True, "kind": step["kind"], "result": {"opened": True}}

        with patch("zero_os.task_executor.execute_step", side_effect=fake_execute_step), patch(
            "zero_os.task_executor.review_run",
            return_value={"decision": "allow", "contradiction_count": 0},
        ):
            out = _execute_plan(str(self.base), "inspect page https://example.com and if inspect verifies then open https://example.com", plan, run_id="run-1")

        self.assertTrue(out["ok"])
        self.assertEqual("web_verify", out["results"][0]["kind"])
        self.assertEqual("browser_open", out["results"][1]["kind"])
        self.assertEqual("on_verified", out["results"][1]["condition_type"])
        self.assertEqual("web_verify", out["results"][1]["conditional_triggered_by"])

    def test_execute_with_replan_prefers_alternate_with_stronger_survivor_history(self) -> None:
        plan = {"branch": {"id": "primary"}, "steps": [{"kind": "browser_open", "target": "https://example.com"}]}
        selection = {
            "discarded_branches": [
                {
                    "decision": "allow",
                    "survivor_history": {"score": 0.22},
                    "plan": {
                        "branch": {"id": "alt_low_history"},
                        "steps": [{"kind": "observe", "target": "status"}],
                        "planner_confidence": 0.7,
                        "target_coverage": {"coverage_ratio": 1.0},
                    },
                },
                {
                    "decision": "allow",
                    "survivor_history": {"score": 0.91},
                    "plan": {
                        "branch": {"id": "alt_high_history"},
                        "steps": [{"kind": "observe", "target": "status"}],
                        "planner_confidence": 0.7,
                        "target_coverage": {"coverage_ratio": 1.0},
                    },
                },
            ]
        }
        executed_branch_ids: list[str] = []

        def fake_execute_plan(_cwd: str, _request: str, selected_plan: dict, **kwargs) -> dict:
            branch_id = str(((selected_plan.get("branch") or {}).get("id", "primary")))
            executed_branch_ids.append(branch_id)
            if len(executed_branch_ids) == 1:
                return {
                    "ok": False,
                    "plan": selected_plan,
                    "results": [{"ok": False, "kind": "browser_open", "reason": "network_unreachable"}],
                    "contradiction_gate": {"decision": "allow", "contradiction_count": 0},
                    "branch_selection": kwargs.get("branch_selection", {}),
                }
            return {
                "ok": True,
                "plan": selected_plan,
                "results": [{"ok": True, "kind": "observe", "result": {"ok": True}}],
                "contradiction_gate": {"decision": "allow", "contradiction_count": 0},
                "branch_selection": kwargs.get("branch_selection", {}),
            }

        with patch("zero_os.task_executor._execute_plan", side_effect=fake_execute_plan):
            out = _execute_with_replan(str(self.base), "open https://example.com", plan, selection)

        self.assertEqual(["primary", "alt_high_history"], executed_branch_ids)
        self.assertTrue(out["replan"]["applied"])
        self.assertEqual("alt_high_history", out["replan"]["candidate_branch_id"])


if __name__ == "__main__":
    unittest.main()
