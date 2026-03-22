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

from zero_os.task_executor import run_task, run_task_resume
from zero_os.recovery import zero_ai_backup_create
from zero_os.api_connector_profiles import profile_set
from zero_os.approval_workflow import decide as approval_decide, status as approval_status
from zero_os.assistant_job_runner import remove_recurring as job_remove_recurring, schedule as job_schedule, schedule_recurring_builtin as job_schedule_recurring_builtin, status as job_status, tick as job_tick
from zero_os.playbook_memory import status as playbook_status
from zero_os.self_continuity import zero_ai_continuity_governance_set


class ZeroAiAssistantStackTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_ai_assistant_")
        self.base = Path(self.tempdir)
        (self.base / ".zero_os").mkdir(parents=True, exist_ok=True)
        (self.base / ".zero_os" / "state.json").write_text("{}", encoding="utf-8")

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_run_task_collects_status(self) -> None:
        out = run_task(str(self.base), "check system status")
        self.assertTrue(out["ok"])
        self.assertTrue(any(step["kind"] == "system_status" for step in out["plan"]["steps"]))

    def test_run_task_verifies_url(self) -> None:
        out = run_task(str(self.base), "check https://example.com")
        self.assertTrue(out["ok"])
        self.assertTrue(any(step["kind"] == "web_verify" for step in out["plan"]["steps"]))
        self.assertFalse(any(step["kind"] == "system_status" for step in out["plan"]["steps"]))

    def test_run_task_autonomy_gate_for_fix(self) -> None:
        out = run_task(str(self.base), "fix runtime issues")
        self.assertTrue(any(step["kind"] == "autonomy_gate" for step in out["plan"]["steps"]))

    def test_run_task_fetches_url(self) -> None:
        out = run_task(str(self.base), "fetch https://example.com")
        self.assertTrue(any(step["kind"] == "web_fetch" for step in out["plan"]["steps"]))
        self.assertEqual(1, sum(1 for step in out["plan"]["steps"] if step["kind"] == "web_verify"))

    def test_run_task_store_status(self) -> None:
        out = run_task(str(self.base), "native store status")
        self.assertTrue(any(step["kind"] == "store_status" for step in out["plan"]["steps"]))

    def test_run_task_recover_executes_with_snapshot(self) -> None:
        zero_ai_backup_create(str(self.base))
        out = run_task(str(self.base), "recover system")
        self.assertTrue(any(step["kind"] == "recover" for step in out["plan"]["steps"]))

    def test_run_task_browser_open_step(self) -> None:
        out = run_task(str(self.base), "open https://example.com")
        self.assertTrue(any(step["kind"] == "browser_open" for step in out["plan"]["steps"]))

    def test_run_task_api_request_step(self) -> None:
        profile_set(str(self.base), "demo", "https://example.com")
        out = run_task(str(self.base), "api profile demo fetch /")
        self.assertTrue(any(step["kind"] == "api_request" for step in out["plan"]["steps"]))

    def test_run_task_returns_synthesized_response(self) -> None:
        out = run_task(str(self.base), "check system status")
        self.assertIn("response", out)
        self.assertIn("summary", out["response"])
        self.assertIn("contradiction_gate", out["response"])
        self.assertIn("contradiction_gate", out)
        self.assertIn("branch_selection", out)
        self.assertIn("task_memory", out)

    def test_run_task_can_use_highway_dispatch(self) -> None:
        out = run_task(str(self.base), "whoami")
        self.assertTrue(any(step["kind"] == "highway_dispatch" for step in out["plan"]["steps"]))

    def test_run_task_browser_status(self) -> None:
        out = run_task(str(self.base), "browser status")
        self.assertTrue(any(step["kind"] == "browser_status" for step in out["plan"]["steps"]))

    def test_run_task_resume_continues_resumable_work(self) -> None:
        out = run_task(str(self.base), "recover system")
        self.assertFalse(out["ok"])
        resumed = run_task_resume(str(self.base))
        self.assertFalse(resumed["ok"] or resumed.get("reason") == "no resumable task")
        self.assertIn("task_memory", resumed)

    def test_run_task_browser_action_can_request_approval(self) -> None:
        out = run_task(str(self.base), "open https://example.com and click")
        approvals = approval_status(str(self.base))
        self.assertTrue(any(step["kind"] == "browser_action" for step in out["plan"]["steps"]))
        self.assertGreaterEqual(approvals["count"], 1)

    def test_approved_browser_action_allows_resume(self) -> None:
        out = run_task(str(self.base), "open https://example.com and click")
        approval = approval_status(str(self.base))["items"][-1]
        approval_decide(str(self.base), approval["id"], True)
        resumed = run_task_resume(str(self.base))
        self.assertTrue(resumed["ok"])
        self.assertIn("task_memory", resumed)
        browser_actions = [item for item in resumed["results"] if item["kind"] == "browser_action"]
        self.assertEqual(1, len(browser_actions))
        self.assertEqual("https://example.com", browser_actions[0]["result"]["action"]["url"])

    def test_resume_without_approval_reuses_existing_browser_request(self) -> None:
        run_task(str(self.base), "open https://example.com and click")
        first_count = approval_status(str(self.base))["count"]

        resumed = run_task_resume(str(self.base))

        self.assertFalse(resumed["ok"])
        self.assertEqual(first_count, approval_status(str(self.base))["count"])

    def test_approved_self_repair_resume_uses_approval_instead_of_looping(self) -> None:
        out = run_task(str(self.base), "self repair runtime")
        self.assertFalse(out["ok"])

        approval = approval_status(str(self.base))["items"][-1]
        approval_decide(str(self.base), approval["id"], True)
        resumed = run_task_resume(str(self.base))

        self.assertFalse(resumed["ok"])
        self.assertEqual("self_repair", resumed["results"][-1]["kind"])
        self.assertNotEqual("approval_required", resumed["results"][-1].get("reason"))
        self.assertEqual(1, approval_status(str(self.base))["count"])

    def test_run_task_api_workflow(self) -> None:
        profile_set(str(self.base), "demo", "https://example.com")
        out = run_task(str(self.base), "api workflow demo paths /,/index.html")
        self.assertTrue(any(step["kind"] == "api_workflow" for step in out["plan"]["steps"]))

    def test_run_task_remembers_playbook(self) -> None:
        run_task(str(self.base), "check system status")
        status = playbook_status(str(self.base))
        self.assertGreaterEqual(status["count"], 1)

    def test_background_job_runner(self) -> None:
        job_schedule(str(self.base), "check system status")
        ticked = job_tick(str(self.base))
        self.assertTrue(ticked["ok"])

    def test_background_job_runner_can_manage_recurring_continuity_governance(self) -> None:
        zero_ai_continuity_governance_set(str(self.base), True, 120)
        scheduled = job_schedule_recurring_builtin(str(self.base), "continuity_governance", interval_seconds=120, enabled=True)
        self.assertTrue(scheduled["ok"])
        status = job_status(str(self.base))
        self.assertGreaterEqual(status["recurring_count"], 1)
        ticked = job_tick(str(self.base))
        self.assertTrue(ticked["ok"])
        self.assertIn("recurring_job", ticked)
        removed = job_remove_recurring(str(self.base), "continuity_governance")
        self.assertTrue(removed["ok"])

    def test_run_task_browser_dom_inspect(self) -> None:
        out = run_task(str(self.base), "inspect page https://example.com")
        self.assertTrue(any(step["kind"] == "browser_dom_inspect" for step in out["plan"]["steps"]))

    def test_run_task_github_connect(self) -> None:
        out = run_task(str(self.base), "github repo connect owner/repo")
        self.assertTrue(any(step["kind"] == "github_connect" for step in out["plan"]["steps"]))

    def test_run_task_cloud_deploy(self) -> None:
        out = run_task(str(self.base), "cloud target set prod provider aws")
        self.assertTrue(any(step["kind"] == "cloud_target_set" for step in out["plan"]["steps"]))

    def test_run_task_find_contradictions_bugs_errors_and_virus_uses_flow_monitor(self) -> None:
        out = run_task(str(self.base), "find contradiction bugs errors virus anything")
        self.assertTrue(any(step["kind"] == "flow_monitor" for step in out["plan"]["steps"]))
        self.assertIn("flow monitor", out["response"]["summary"])

    def test_run_task_smart_workspace_uses_workspace_lane(self) -> None:
        out = run_task(str(self.base), "smart workspace")
        self.assertTrue(any(step["kind"] == "smart_workspace" for step in out["plan"]["steps"]))
        self.assertIn("smart workspace", out["response"]["summary"])

    def test_run_task_maintenance_uses_maintenance_lane(self) -> None:
        out = run_task(str(self.base), "maintenance status")
        self.assertTrue(any(step["kind"] == "maintenance_orchestrator" for step in out["plan"]["steps"]))
        self.assertIn("maintenance orchestrator", out["response"]["summary"])

    def test_run_task_internet_uses_internet_lane(self) -> None:
        out = run_task(str(self.base), "internet status")
        self.assertTrue(any(step["kind"] == "internet_capability" for step in out["plan"]["steps"]))
        self.assertIn("internet capability", out["response"]["summary"])

    def test_run_task_world_class_readiness_uses_readiness_lane(self) -> None:
        out = run_task(str(self.base), "world class readiness")
        self.assertTrue(any(step["kind"] == "world_class_readiness" for step in out["plan"]["steps"]))
        self.assertIn("world class readiness", out["response"]["summary"])

    def test_run_task_contradiction_status_uses_reasoning_subsystem(self) -> None:
        out = run_task(str(self.base), "contradiction status")
        self.assertEqual(["contradiction_engine"], [step["kind"] for step in out["plan"]["steps"]])
        self.assertIn("contradiction gate", out["response"]["summary"])

    def test_run_task_pressure_harness_uses_pressure_lane(self) -> None:
        out = run_task(str(self.base), "pressure harness")
        self.assertTrue(out["ok"])
        self.assertEqual(["pressure_harness"], [step["kind"] for step in out["plan"]["steps"]])
        self.assertIn("pressure harness", out["response"]["summary"])

    def test_run_task_capability_expansion_protocol_uses_expansion_lane(self) -> None:
        out = run_task(str(self.base), "zero ai capability expansion protocol status")
        self.assertTrue(out["ok"])
        self.assertEqual(["capability_expansion_protocol"], [step["kind"] for step in out["plan"]["steps"]])
        self.assertIn("capability_expansion_protocol", out["response"]["summary"])

    def test_run_task_general_agent_uses_general_agent_lane(self) -> None:
        out = run_task(str(self.base), "make zero ai can do agentic general-purpose ai")
        self.assertTrue(out["ok"])
        self.assertEqual(["general_agent"], [step["kind"] for step in out["plan"]["steps"]])
        self.assertIn("general agent", out["response"]["summary"])

    def test_run_task_feature_request_routes_to_feature_generator(self) -> None:
        out = run_task(str(self.base), "add feature billing reminder follow up workflow")
        self.assertTrue(out["ok"])
        self.assertEqual(["domain_pack_generate_feature"], [step["kind"] for step in out["plan"]["steps"]])
        self.assertIn("feature generator", out["response"]["summary"])

    def test_run_task_holds_output_when_continuity_has_contradiction(self) -> None:
        runtime_dir = self.base / ".zero_os" / "runtime"
        runtime_dir.mkdir(parents=True, exist_ok=True)
        (runtime_dir / "zero_ai_self_continuity.json").write_text(
            json.dumps(
                {
                    "continuity": {"same_system": True, "continuity_score": 82.0},
                    "contradiction_detection": {
                        "has_contradiction": True,
                        "issues": ["self_model_missing_no_contradiction_constraint"],
                    },
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        out = run_task(str(self.base), "check system status")
        self.assertFalse(out["ok"])
        self.assertEqual("hold", out["contradiction_gate"]["decision"])
        self.assertIn("contradiction gate: hold", out["response"]["summary"])

    def test_run_task_does_not_bleed_previous_playbook_steps_into_new_request(self) -> None:
        first = run_task(str(self.base), "check system status")
        self.assertTrue(first["ok"])

        second = run_task(str(self.base), "browser status and inspect page https://example.com")
        self.assertEqual(
            ["web_verify", "browser_status", "browser_dom_inspect"],
            [step["kind"] for step in second["plan"]["steps"]],
        )

    def test_run_task_deduplicates_repeated_urls_in_one_request(self) -> None:
        out = run_task(str(self.base), "check https://example.com and open https://example.com and click")
        self.assertEqual(
            ["web_verify", "web_fetch", "browser_open", "browser_action"],
            [step["kind"] for step in out["plan"]["steps"]],
        )

    def test_run_task_highest_value_steps_uses_controller_registry(self) -> None:
        out = run_task(str(self.base), "highest value steps")
        self.assertTrue(out["ok"])
        self.assertTrue(any(step["kind"] == "controller_registry" for step in out["plan"]["steps"]))
        self.assertIn("controller registry", out["response"]["summary"])

    def test_run_task_regenerates_conflicting_recovery_request_into_single_branch(self) -> None:
        zero_ai_backup_create(str(self.base))
        out = run_task(str(self.base), "recover system and self repair runtime")

        remediation_kinds = [step["kind"] for step in out["plan"]["steps"] if step["kind"] in {"recover", "self_repair"}]
        self.assertEqual(["recover"], remediation_kinds)
        self.assertGreaterEqual(out["branch_selection"]["discarded_count"], 1)
        self.assertEqual("single_recover", out["branch_selection"]["selected_branch"]["branch"]["id"])

    def test_run_task_surfaces_memory_weighted_branch_support(self) -> None:
        first = run_task(str(self.base), "check system status")
        self.assertTrue(first["ok"])

        second = run_task(str(self.base), "check system status")
        selected = second["branch_selection"]["selected_branch"]

        self.assertGreater(float(selected["evidence"]["memory_weight"]), 0.0)
        self.assertGreater(float(selected["memory_context"]["memory_confidence"]), 0.0)


if __name__ == "__main__":
    unittest.main()
