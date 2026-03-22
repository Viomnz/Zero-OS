import shutil
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from zero_os.task_executor import run_task
from zero_os.task_planner import build_candidate_plans, build_plan, planner_feedback_status, smart_planner_assess, smart_planner_status


class TaskPlannerUpgradeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="task_planner_upgrade_")
        self.base = Path(self.tempdir)
        (self.base / ".zero_os").mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_build_plan_exposes_confidence_and_target_coverage(self) -> None:
        plan = build_plan("open https://example.com and click", str(self.base))

        self.assertEqual("2026.03.22", plan["planner_version"])
        self.assertGreater(float(plan["planner_confidence"]), 0.0)
        self.assertIn("intent_scores", plan)
        self.assertIn("risk_level", plan)
        self.assertIn("target_coverage", plan)
        self.assertEqual(1.0, float(plan["target_coverage"]["coverage_ratio"]))
        self.assertTrue(any(step["kind"] == "browser_action" for step in plan["steps"]))
        self.assertEqual([], plan["dropped_targets"])
        self.assertEqual(plan["ambiguity_flags"], plan["ambiguity"])

    def test_build_plan_preserves_browser_status_and_inspect_routes(self) -> None:
        plan = build_plan("browser status and inspect page https://example.com", str(self.base))

        self.assertEqual(
            ["web_verify", "browser_status", "browser_dom_inspect"],
            [step["kind"] for step in plan["steps"]],
        )
        self.assertEqual("web", plan["intent"]["primary_intent"])
        self.assertIn("browser", plan["intent"]["secondary_intents"])
        self.assertEqual("low", plan["risk_level"])

    def test_build_candidate_plans_adds_target_specific_and_memory_variants(self) -> None:
        bundle = build_candidate_plans(
            "check https://example.com and open https://other.example and click",
            str(self.base),
        )

        branch_ids = {candidate["branch"]["id"] for candidate in bundle["candidates"]}
        self.assertIn("primary", branch_ids)
        self.assertTrue(any(branch_id.startswith("single_target_") for branch_id in branch_ids))
        self.assertGreaterEqual(bundle["candidate_count"], 3)

    def test_conflicting_remediation_request_keeps_single_branch_shape(self) -> None:
        plan = build_plan("recover system and self repair runtime", str(self.base))
        bundle = build_candidate_plans("recover system and self repair runtime", str(self.base), base_plan=plan)

        self.assertEqual("single_recover", plan["branch"]["id"])
        branch_ids = {candidate["branch"]["id"] for candidate in bundle["candidates"]}
        self.assertIn("single_recover", branch_ids)
        self.assertIn("single_self_repair", branch_ids)

    def test_read_only_phrase_drops_mutation_from_primary_branch(self) -> None:
        plan = build_plan("show browser status for https://example.com and inspect page https://example.com", str(self.base))

        self.assertFalse(any(step["kind"] == "browser_action" for step in plan["steps"]))
        self.assertFalse(any(step["kind"] == "browser_open" for step in plan["steps"]))
        self.assertTrue(plan["read_only_request"])

    def test_build_plan_parses_github_action_and_reply_targets(self) -> None:
        plan = build_plan(
            "github issue reply post octo/test 12 text=Ship the fix and github pr act octo/test 34 execute=true",
            str(self.base),
        )

        steps_by_kind = {step["kind"]: step["target"] for step in plan["steps"]}
        self.assertIn("github_issue_reply_post", steps_by_kind)
        self.assertIn("github_pr_act", steps_by_kind)
        self.assertEqual("octo/test", steps_by_kind["github_issue_reply_post"]["repo"])
        self.assertEqual(12, steps_by_kind["github_issue_reply_post"]["issue"])
        self.assertEqual("Ship the fix", steps_by_kind["github_issue_reply_post"]["text"])
        self.assertTrue(steps_by_kind["github_pr_act"]["execute"])

    def test_build_plan_keeps_browser_selector_and_value(self) -> None:
        plan = build_plan(
            "open https://example.com and input selector=#search value=hello world",
            str(self.base),
        )

        browser_actions = [step for step in plan["steps"] if step["kind"] == "browser_action"]
        self.assertEqual(1, len(browser_actions))
        self.assertEqual("#search", browser_actions[0]["target"]["selector"])
        self.assertEqual("hello world", browser_actions[0]["target"]["value"])
        self.assertNotIn("browser_action_missing_value", plan["ambiguity_flags"])
        self.assertEqual("ready", browser_actions[0]["precondition_state"])
        self.assertGreater(browser_actions[0]["confidence"], 0.0)

    def test_build_plan_adds_global_targets_and_overlap_flags(self) -> None:
        plan = build_plan("show file src/main.py and open https://example.com", str(self.base))

        self.assertTrue(plan["targets"]["files"])
        self.assertTrue(plan["targets"]["actions"])
        self.assertIn("read_only_mutation_overlap", plan["ambiguity_flags"])
        self.assertTrue(any(step["kind"] == "highway_dispatch" for step in plan["steps"]))
        self.assertEqual(1.0, float(plan["target_coverage"]["coverage_ratio"]))

    def test_build_plan_adds_low_target_signal_for_targetless_web_request(self) -> None:
        plan = build_plan("open browser and click", str(self.base))

        self.assertIn("low_target_signal", plan["ambiguity_flags"])

    def test_build_plan_blocks_missing_browser_input_value_at_planner_stage(self) -> None:
        plan = build_plan("open https://example.com and input selector=#search", str(self.base))

        browser_actions = [step for step in plan["steps"] if step["kind"] == "browser_action"]
        self.assertEqual([], browser_actions)
        self.assertIn("browser_action_missing_value", plan["ambiguity_flags"])

    def test_planner_feedback_status_aggregates_multiple_routes(self) -> None:
        run_task(str(self.base), "browser status")
        run_task(str(self.base), "world class readiness")

        status = planner_feedback_status(str(self.base))

        self.assertGreaterEqual(status["summary"]["history_count"], 2)
        self.assertIn("web", status["summary"]["routes"])
        self.assertIn("world_class_readiness", status["summary"]["routes"])

    def test_build_plan_keeps_file_and_deploy_targets_attached(self) -> None:
        plan = build_plan(
            "cloud target set prod provider aws and deploy artifact build/app.zip to prod and show file deploy.yaml",
            str(self.base),
        )

        self.assertTrue(any(step["kind"] == "cloud_target_set" for step in plan["steps"]))
        self.assertTrue(any(step["kind"] == "cloud_deploy" for step in plan["steps"]))
        self.assertTrue(any(step["kind"] == "highway_dispatch" and "deploy.yaml" in str(step["target"]) for step in plan["steps"]))
        self.assertEqual(1.0, float(plan["target_coverage"]["coverage_ratio"]))

    def test_build_candidate_plans_adds_single_target_branches_for_files_and_deployments(self) -> None:
        bundle = build_candidate_plans(
            "cloud target set prod provider aws and deploy artifact build/app.zip to prod and show file deploy.yaml",
            str(self.base),
        )

        branch_ids = {candidate["branch"]["id"] for candidate in bundle["candidates"]}
        self.assertTrue(any(branch_id.startswith("single_target_files_") for branch_id in branch_ids))
        self.assertTrue(any(branch_id.startswith("single_target_deployments_") for branch_id in branch_ids))

    def test_build_plan_respects_after_dependency_in_subgoal_ordering(self) -> None:
        plan = build_plan("open https://example.com after inspect page https://example.com", str(self.base))

        step_kinds = [step["kind"] for step in plan["steps"]]
        self.assertLess(step_kinds.index("browser_dom_inspect"), step_kinds.index("browser_open"))
        subgoals = {item["id"]: item for item in plan["request_decomposition"]}
        self.assertEqual(["subgoal_1"], subgoals["subgoal_0"]["depends_on"])
        self.assertEqual("prerequisite", subgoals["subgoal_1"]["dependency_kind"])

    def test_build_plan_applies_route_history_bias_to_intent_scores(self) -> None:
        baseline = build_plan("browser status", str(self.base))
        planner_feedback_path = self.base / ".zero_os" / "assistant" / "planner_feedback.json"
        planner_feedback_path.parent.mkdir(parents=True, exist_ok=True)
        planner_feedback_path.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "history": [],
                    "summary": {
                        "routes": {
                            "web": {
                                "count": 5,
                                "contradiction_hold_rate": 0.8,
                                "execution_failure_rate": 0.6,
                                "approval_required_surprise_rate": 0.2,
                                "target_drop_rate": 0.4,
                                "successful_completion_rate": 0.2,
                                "reroute_after_failure_rate": 0.5,
                            },
                            "browser": {
                                "count": 5,
                                "contradiction_hold_rate": 0.0,
                                "execution_failure_rate": 0.0,
                                "approval_required_surprise_rate": 0.0,
                                "target_drop_rate": 0.0,
                                "successful_completion_rate": 1.0,
                                "reroute_after_failure_rate": 0.0,
                            },
                        }
                    },
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        biased = build_plan("browser status", str(self.base))

        self.assertLess(float(biased["intent_scores"]["web"]), float(baseline["intent_scores"]["web"]))
        self.assertGreater(float(biased["intent_scores"]["browser"]), float(baseline["intent_scores"]["browser"]))
        self.assertLess(float(biased["route_history_bias"]["web"]), 0.0)
        self.assertGreater(float(biased["route_history_bias"]["browser"]), 0.0)

    def test_build_candidate_plans_compresses_near_duplicate_balanced_branches(self) -> None:
        bundle = build_candidate_plans("open https://example.com after inspect page https://example.com", str(self.base))

        balanced_signatures: dict[tuple[tuple[str, str], ...], int] = {}
        for candidate in bundle["candidates"]:
            if candidate["branch"]["memory_mode"] != "balanced":
                continue
            signature = tuple(sorted((step["kind"], str(step["target"])) for step in candidate["steps"]))
            balanced_signatures[signature] = balanced_signatures.get(signature, 0) + 1
        self.assertTrue(all(count == 1 for count in balanced_signatures.values()))

    def test_build_plan_adds_mutation_justification_on_mutating_steps(self) -> None:
        plan = build_plan("open https://example.com and click", str(self.base))

        mutating_steps = [step for step in plan["steps"] if step["kind"] in {"browser_open", "browser_action"}]
        self.assertEqual(2, len(mutating_steps))
        self.assertTrue(all(step["mutation_requested_explicitly"] for step in mutating_steps))
        self.assertTrue(all(step["mutation_allowed_with_justification"] for step in mutating_steps))
        self.assertTrue(all(str(step["mutation_justification"]).strip() for step in mutating_steps))

    def test_build_plan_includes_smart_planner_profile(self) -> None:
        plan = build_plan(
            "open https://example.com after inspect page https://example.com and then deploy artifact build/app.zip to prod",
            str(self.base),
        )

        smart = dict(plan["smart_planner"])
        self.assertIn(smart["strategy"], {"dependency_aware", "verification_first"})
        self.assertTrue(smart["requires_dependency_tracking"])
        self.assertGreaterEqual(float(smart["complexity_score"]), 0.45)
        self.assertTrue((self.base / ".zero_os" / "assistant" / "smart_planner.json").exists())

    def test_smart_planner_status_and_assess_surface_latest_profile(self) -> None:
        assessed = smart_planner_assess("open https://example.com and click", str(self.base))
        status = smart_planner_status(str(self.base))

        self.assertTrue(assessed["ok"])
        self.assertIn("smart_planner", assessed)
        self.assertTrue(status["ok"])
        self.assertEqual(assessed["smart_planner"]["strategy"], status["latest"]["strategy"])
        self.assertIn("planner_feedback_history_count", status)


if __name__ == "__main__":
    unittest.main()
