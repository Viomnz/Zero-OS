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
from zero_os.task_planner import (
    build_candidate_plans,
    build_plan,
    planner_feedback_status,
    record_planner_outcome,
    self_derivation_assess,
    self_derivation_status,
    smart_planner_assess,
    smart_planner_status,
)


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
        self.assertTrue(plan["semantic_interpretations"])
        self.assertTrue(plan["semantic_frame"])
        self.assertTrue(plan["semantic_roles"])
        self.assertTrue(plan["semantic_goal"])
        self.assertTrue(plan["semantic_abstraction"])
        self.assertTrue(plan["semantic_abstraction"]["structure_family"])

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
        self.assertIn("rejected_candidates", bundle)

    def test_build_candidate_plans_rejects_predicted_bad_branch_early(self) -> None:
        plan = build_plan("open https://example.com and click", str(self.base))
        bad_action = next(step for step in plan["steps"] if step["kind"] == "browser_action")
        bad_action = dict(bad_action)
        bad_action["target"] = {"action": "click", "url": "", "selector": ""}
        bad_action["route_confidence"] = 0.1
        bad_action["confidence"] = 0.1
        plan["steps"] = [bad_action]

        bundle = build_candidate_plans("open https://example.com and click", str(self.base), base_plan=plan)

        self.assertTrue(bundle["rejected_candidates"])
        primary_rejections = [candidate for candidate in bundle["rejected_candidates"] if candidate["branch"]["id"] == "primary"]
        self.assertTrue(primary_rejections)
        self.assertTrue(primary_rejections[0]["branch_rejection"]["rejected"])
        self.assertTrue(primary_rejections[0]["branch_rejection"]["reasons"])

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
        self.assertIn("self_derivation", bundle)
        self.assertGreaterEqual(int(bundle["self_derivation"]["generated_count"]), 10)
        self.assertGreaterEqual(int(bundle["self_derivation"]["survivor_count"]), 1)
        self.assertIn(bundle["self_derivation"]["recommended_branch_id"], branch_ids)

    def test_build_candidate_plans_adds_survivor_guided_branch_from_history(self) -> None:
        derivation_dir = self.base / ".zero_os" / "assistant" / "self_derivation"
        derivation_dir.mkdir(parents=True, exist_ok=True)
        (derivation_dir / "memory.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "patterns": {
                        "mutate -> prepare -> verify": {
                            "pattern_signature": "mutate -> prepare -> verify",
                            "survival_count": 5,
                            "average_score": 91.0,
                            "contexts": ['{"goal": "mutate_resource", "shape": "mixed_target", "targets": ["actions", "urls"]}'],
                            "context_range": 1,
                            "failure_conditions": [],
                            "structure": "mutate -> prepare -> verify",
                            "source_branch_ids": ["historical_mutate_first"],
                        }
                    },
                    "knowledge": [],
                    "meta_rules": [],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        bundle = build_candidate_plans("open https://example.com and click", str(self.base))

        self.assertIn("survivor_guidance", bundle)
        self.assertTrue(bundle["survivor_guidance"]["recommended_patterns"])
        guided = [candidate for candidate in bundle["candidates"] if candidate["branch"]["source"] == "survivor_history_generation"]
        self.assertTrue(guided)
        self.assertGreater(float(guided[0]["survivor_history_prior"]["score"]), 0.0)
        step_kinds = [step["kind"] for step in guided[0]["steps"]]
        self.assertLess(step_kinds.index("browser_action"), step_kinds.index("browser_open"))

    def test_build_plan_applies_safe_survivor_guidance_to_primary_branch(self) -> None:
        derivation_dir = self.base / ".zero_os" / "assistant" / "self_derivation"
        derivation_dir.mkdir(parents=True, exist_ok=True)
        (derivation_dir / "memory.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "patterns": {
                        "verify -> dispatch -> prepare": {
                            "pattern_signature": "verify -> dispatch -> prepare",
                            "survival_count": 6,
                            "average_score": 92.0,
                            "contexts": ['{"goal": "inspect_then_mutate_resource", "shape": "mixed_target", "targets": ["actions", "files", "urls"]}'],
                            "context_range": 1,
                            "failure_conditions": [],
                            "structure": "verify -> dispatch -> prepare",
                            "source_branch_ids": ["historical_safe_guidance"],
                        }
                    },
                    "knowledge": [],
                    "meta_rules": [],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        plan = build_plan("show file src/main.py and open https://example.com", str(self.base))

        self.assertTrue(plan["survivor_guidance_applied"])
        self.assertEqual("verify -> dispatch -> prepare", plan["survivor_guidance_pattern"])
        self.assertEqual("weighted_intent_resolution_survivor_guided", plan["branch"]["source"])
        self.assertGreater(float(plan["survivor_history_prior"]["score"]), 0.0)
        step_kinds = [step["kind"] for step in plan["steps"]]
        self.assertLess(step_kinds.index("web_fetch"), step_kinds.index("highway_dispatch"))

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

    def test_build_plan_applies_route_variant_history_bias_for_github_surfaces(self) -> None:
        planner_feedback_path = self.base / ".zero_os" / "assistant" / "planner_feedback.json"
        planner_feedback_path.parent.mkdir(parents=True, exist_ok=True)
        planner_feedback_path.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "history": [],
                    "summary": {
                        "routes": {"github": {"count": 4, "contradiction_hold_rate": 0.0, "execution_failure_rate": 0.0, "approval_required_surprise_rate": 0.0, "target_drop_rate": 0.0, "successful_completion_rate": 1.0, "reroute_after_failure_rate": 0.0}},
                        "route_variants": {
                            "github_issue_read": {
                                "count": 4,
                                "contradiction_hold_rate": 0.0,
                                "execution_failure_rate": 0.0,
                                "approval_required_surprise_rate": 0.0,
                                "target_drop_rate": 0.0,
                                "successful_completion_rate": 1.0,
                                "reroute_after_failure_rate": 0.0,
                            },
                            "github_pr_read": {
                                "count": 4,
                                "contradiction_hold_rate": 0.75,
                                "execution_failure_rate": 0.5,
                                "approval_required_surprise_rate": 0.0,
                                "target_drop_rate": 0.25,
                                "successful_completion_rate": 0.25,
                                "reroute_after_failure_rate": 0.5,
                            },
                        },
                    },
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        issue_plan = build_plan("github issue read octo/test 12", str(self.base))
        pr_plan = build_plan("github pr read octo/test 34", str(self.base))

        self.assertEqual("github_issue_read", issue_plan["route_variant"])
        self.assertGreater(float(issue_plan["route_variant_history_bias"]), 0.0)
        self.assertEqual("github_pr_read", pr_plan["route_variant"])
        self.assertLess(float(pr_plan["route_variant_history_bias"]), 0.0)

    def test_record_planner_outcome_tracks_route_variants_separately(self) -> None:
        issue_plan = build_plan("github issue read octo/test 12", str(self.base))
        pr_plan = build_plan("github pr read octo/test 34", str(self.base))

        record_planner_outcome(
            str(self.base),
            issue_plan["request"],
            {"selected_plan": issue_plan, "discarded_count": 0},
            {"ok": True, "plan": issue_plan, "results": [{"ok": True, "kind": "github_issue_read"}], "contradiction_gate": {"decision": "allow"}},
        )
        record_planner_outcome(
            str(self.base),
            pr_plan["request"],
            {"selected_plan": pr_plan, "discarded_count": 0},
            {"ok": True, "plan": pr_plan, "results": [{"ok": True, "kind": "github_pr_read"}], "contradiction_gate": {"decision": "allow"}},
        )

        status = planner_feedback_status(str(self.base))

        self.assertIn("route_variants", status["summary"])
        self.assertIn("github_issue_read", status["summary"]["route_variants"])
        self.assertIn("github_pr_read", status["summary"]["route_variants"])
        self.assertEqual(1, int(status["summary"]["route_variants"]["github_issue_read"]["count"]))
        self.assertEqual(1, int(status["summary"]["route_variants"]["github_pr_read"]["count"]))

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
        self.assertIn(smart["strategy_mode"], {"safe", "exploratory", "aggressive", "fast"})
        self.assertTrue(smart["requires_dependency_tracking"])
        self.assertGreaterEqual(float(smart["complexity_score"]), 0.45)
        self.assertTrue((self.base / ".zero_os" / "assistant" / "smart_planner.json").exists())

    def test_build_plan_uses_cross_context_survivor_guidance_for_strategy(self) -> None:
        derivation_dir = self.base / ".zero_os" / "assistant" / "self_derivation"
        derivation_dir.mkdir(parents=True, exist_ok=True)
        (derivation_dir / "memory.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "patterns": {
                        "verify -> prepare -> mutate": {
                            "pattern_signature": "verify -> prepare -> mutate",
                            "survival_count": 6,
                            "average_score": 90.0,
                            "contexts": ['{"goal": "mutate_resource", "shape": "single_step", "targets": ["actions", "urls"]}'],
                            "abstract_contexts": ['{"semantic_goal": "mutate_resource", "structure_family": "verify_then_mutate_pattern", "target_families": ["interaction_surface", "remote_source"]}'],
                            "validated_abstract_contexts": ['{"semantic_goal": "mutate_resource", "structure_family": "verify_then_mutate_pattern", "target_families": ["interaction_surface", "remote_source"]}'],
                            "context_range": 1,
                            "validated_context_count": 2,
                            "cross_context_score": 0.86,
                            "failure_conditions": [],
                            "structure": "verify -> prepare -> mutate",
                            "source_branch_ids": ["historical_verify_pattern"],
                        }
                    },
                    "knowledge": [],
                    "meta_rules": [
                        {
                            "rule": "verification_first_survives_better",
                            "confidence": 0.92,
                            "evidence": {"verification_first_average": 92.0, "mutate_first_average": 61.0},
                        }
                    ],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        plan = build_plan("open https://example.com and click", str(self.base))

        self.assertEqual("verification_first", plan["smart_planner"]["strategy"])
        self.assertIn("survivor_strategy_guidance", plan["smart_planner"]["reasons"])
        self.assertEqual("verification_first", plan["survivor_strategy_guidance"]["preferred_strategy"])
        self.assertGreater(float(plan["survivor_strategy_guidance"]["cross_context_score"]), 0.0)

    def test_build_candidate_plans_uses_survivor_strategy_guidance_to_expand_branch_mix(self) -> None:
        derivation_dir = self.base / ".zero_os" / "assistant" / "self_derivation"
        derivation_dir.mkdir(parents=True, exist_ok=True)
        (derivation_dir / "memory.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "patterns": {
                        "observe": {
                            "pattern_signature": "observe",
                            "survival_count": 7,
                            "average_score": 88.0,
                            "contexts": ['{"goal": "mutate_resource", "shape": "single_step", "targets": ["actions", "urls"]}'],
                            "abstract_contexts": ['{"semantic_goal": "mutate_resource", "structure_family": "observation_first_pattern", "target_families": ["interaction_surface", "remote_source"]}'],
                            "validated_abstract_contexts": ['{"semantic_goal": "mutate_resource", "structure_family": "observation_first_pattern", "target_families": ["interaction_surface", "remote_source"]}'],
                            "context_range": 1,
                            "validated_context_count": 2,
                            "cross_context_score": 0.79,
                            "failure_conditions": [],
                            "structure": "observe",
                            "source_branch_ids": ["historical_observe_pattern"],
                        }
                    },
                    "knowledge": [],
                    "meta_rules": [],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        bundle = build_candidate_plans("open https://example.com and click", str(self.base))

        self.assertEqual("conservative", bundle["survivor_strategy_guidance"]["preferred_strategy"])
        branch_ids = {candidate["branch"]["id"] for candidate in bundle["candidates"]}
        self.assertIn("minimal_safe", branch_ids)
        self.assertIn("conservative_execution", branch_ids)

    def test_build_plan_uses_strategy_outcomes_for_top_level_strategy_when_pattern_guidance_is_weak(self) -> None:
        derivation_dir = self.base / ".zero_os" / "assistant" / "self_derivation"
        derivation_dir.mkdir(parents=True, exist_ok=True)
        (derivation_dir / "memory.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "patterns": {},
                    "knowledge": [],
                    "strategy_outcomes": {
                        "verification_first": {
                            "strategy": "verification_first",
                            "run_count": 4,
                            "success_count": 4,
                            "failure_count": 0,
                            "recovery_count": 1,
                            "contradiction_hold_count": 0,
                            "reroute_count": 1,
                            "success_rate": 1.0,
                            "failure_rate": 0.0,
                            "recovery_rate": 0.25,
                            "contradiction_hold_rate": 0.0,
                            "average_outcome_quality": 0.91,
                            "resilience_score": 0.9,
                            "last_outcome": {"ok": True},
                        }
                    },
                    "meta_rules": [],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        plan = build_plan("open https://example.com and click", str(self.base))

        self.assertEqual("verification_first", plan["smart_planner"]["strategy"])
        self.assertEqual("verification_first", plan["survivor_strategy_guidance"]["preferred_strategy"])
        self.assertTrue(plan["survivor_strategy_guidance"]["outcome_guided"])
        self.assertEqual("verification_first", plan["survivor_strategy_guidance"]["outcome_guided_strategy"])
        self.assertIn("strategy_outcome_guidance", plan["smart_planner"]["reasons"])

    def test_build_plan_decays_stale_strategy_outcome_guidance(self) -> None:
        derivation_dir = self.base / ".zero_os" / "assistant" / "self_derivation"
        derivation_dir.mkdir(parents=True, exist_ok=True)
        (derivation_dir / "memory.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "patterns": {},
                    "knowledge": [],
                    "strategy_outcomes": {
                        "verification_first": {
                            "strategy": "verification_first",
                            "run_count": 4,
                            "success_count": 4,
                            "failure_count": 0,
                            "recovery_count": 1,
                            "contradiction_hold_count": 0,
                            "reroute_count": 1,
                            "success_rate": 1.0,
                            "failure_rate": 0.0,
                            "recovery_rate": 0.25,
                            "contradiction_hold_rate": 0.0,
                            "average_outcome_quality": 0.91,
                            "resilience_score": 0.9,
                            "first_run_utc": "2025-06-01T00:00:00+00:00",
                            "last_run_utc": "2025-06-01T00:00:00+00:00",
                            "last_outcome": {"ok": True},
                        }
                    },
                    "meta_rules": [],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        plan = build_plan("open https://example.com and click", str(self.base))

        self.assertEqual("target_isolated", plan["smart_planner"]["strategy"])
        self.assertFalse(plan["survivor_strategy_guidance"]["outcome_guided"])
        self.assertLess(float(plan["survivor_strategy_guidance"]["strategy_outcome_summary"].get("freshness_score", 0.45) or 0.45), 0.2)

    def test_build_plan_decays_version_mismatched_strategy_outcome_guidance(self) -> None:
        derivation_dir = self.base / ".zero_os" / "assistant" / "self_derivation"
        derivation_dir.mkdir(parents=True, exist_ok=True)
        (derivation_dir / "memory.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "patterns": {},
                    "knowledge": [],
                    "strategy_outcomes": {
                        "verification_first": {
                            "strategy": "verification_first",
                            "planner_version": "2025.12.01",
                            "code_version": "planner:2025.12.01|self_derivation:2025.12.01",
                            "run_count": 4,
                            "success_count": 4,
                            "failure_count": 0,
                            "recovery_count": 1,
                            "contradiction_hold_count": 0,
                            "reroute_count": 1,
                            "success_rate": 1.0,
                            "failure_rate": 0.0,
                            "recovery_rate": 0.25,
                            "contradiction_hold_rate": 0.0,
                            "average_outcome_quality": 0.91,
                            "resilience_score": 0.9,
                            "last_outcome": {"ok": True},
                        }
                    },
                    "meta_rules": [],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        plan = build_plan("open https://example.com and click", str(self.base))

        self.assertEqual("target_isolated", plan["smart_planner"]["strategy"])
        self.assertFalse(plan["survivor_strategy_guidance"]["outcome_guided"])
        self.assertLess(float(plan["survivor_strategy_guidance"]["strategy_outcome_summary"].get("version_alignment_score", 1.0) or 1.0), 0.3)

    def test_build_plan_distinguishes_fragile_but_recoverable_from_fragile_and_unsafe(self) -> None:
        derivation_dir = self.base / ".zero_os" / "assistant" / "self_derivation"
        derivation_dir.mkdir(parents=True, exist_ok=True)

        recoverable_memory = {
            "schema_version": 1,
            "patterns": {},
            "knowledge": [],
            "strategy_outcomes": {
                "verification_first": {
                    "strategy": "verification_first",
                    "run_count": 5,
                    "success_count": 2,
                    "failure_count": 3,
                    "recovery_count": 3,
                    "contradiction_hold_count": 0,
                    "reroute_count": 3,
                    "success_rate": 0.4,
                    "failure_rate": 0.6,
                    "recovery_rate": 0.6,
                    "contradiction_hold_rate": 0.0,
                    "average_outcome_quality": 0.72,
                    "resilience_score": 0.66,
                    "last_outcome": {"ok": False, "recovered": True},
                }
            },
            "meta_rules": [],
        }
        (derivation_dir / "memory.json").write_text(json.dumps(recoverable_memory, indent=2) + "\n", encoding="utf-8")
        recoverable_plan = build_plan("open https://example.com and click", str(self.base))

        self.assertEqual("verification_first", recoverable_plan["smart_planner"]["strategy"])
        self.assertEqual("safe", recoverable_plan["smart_planner"]["strategy_mode"])
        self.assertEqual("fragile_but_recoverable", recoverable_plan["survivor_strategy_guidance"]["recovery_profile"])
        self.assertIn("high", recoverable_plan["survivor_strategy_guidance"]["suppressed_mutation_intensities"])

        unsafe_memory = {
            "schema_version": 1,
            "patterns": {},
            "knowledge": [],
            "strategy_outcomes": {
                "verification_first": {
                    "strategy": "verification_first",
                    "run_count": 5,
                    "success_count": 1,
                    "failure_count": 4,
                    "recovery_count": 1,
                    "contradiction_hold_count": 2,
                    "reroute_count": 1,
                    "success_rate": 0.2,
                    "failure_rate": 0.8,
                    "recovery_rate": 0.2,
                    "contradiction_hold_rate": 0.4,
                    "average_outcome_quality": 0.31,
                    "resilience_score": 0.22,
                    "last_outcome": {"ok": False, "recovered": False},
                }
            },
            "meta_rules": [],
        }
        (derivation_dir / "memory.json").write_text(json.dumps(unsafe_memory, indent=2) + "\n", encoding="utf-8")
        unsafe_plan = build_plan("open https://example.com and click", str(self.base))

        self.assertEqual("conservative", unsafe_plan["smart_planner"]["strategy"])
        self.assertEqual("fragile_and_unsafe", unsafe_plan["survivor_strategy_guidance"]["recovery_profile"])
        self.assertEqual("conservative", unsafe_plan["survivor_strategy_guidance"]["preferred_strategy"])
        self.assertIn("recovery_profile:fragile_and_unsafe", unsafe_plan["smart_planner"]["reasons"])

    def test_build_plan_adds_reasoning_trace_phases_explanation_and_causality(self) -> None:
        plan = build_plan(
            "open https://example.com after inspect page https://example.com and then deploy artifact build/app.zip to prod",
            str(self.base),
        )

        self.assertIn("reasoning_trace", plan)
        self.assertIn(plan["reasoning_trace"]["request_shape"], {"dependency_chain", "multi_stage"})
        self.assertIn("planner_precheck", plan)
        self.assertIn("execution_mode", plan)
        self.assertIn(plan["execution_mode"], {"safe", "deliberate", "normal", "fast"})
        self.assertTrue(plan["phases"])
        self.assertIn("prepare", [phase["name"] for phase in plan["phases"]])
        self.assertIn("plan_simulation", plan)
        self.assertIn("predicted_risk", plan)
        self.assertIn("expected_success", plan)
        self.assertIn("self_critique", plan)
        self.assertIn("explanation", plan)
        self.assertTrue(str(plan["explanation"]["intent_reason"]).strip())
        self.assertTrue(str(plan["explanation"]["risk_reason"]).strip())
        self.assertTrue(str(plan["explanation"]["confidence_reason"]).strip())

        dependent_steps = [step for step in plan["steps"] if step.get("dependent_step_count", 0) or step.get("invalidates_if_failed")]
        self.assertTrue(dependent_steps)
        self.assertTrue(all("dependency_strength" in step for step in dependent_steps))
        self.assertTrue(all(isinstance(step.get("failure_impact"), dict) for step in dependent_steps))
        self.assertTrue(all("mode" in step["failure_impact"] for step in dependent_steps))
        self.assertTrue(all("requires" in step for step in plan["steps"]))
        self.assertTrue(all("enables" in step for step in plan["steps"]))
        self.assertTrue(all("breaks_if_failed" in step for step in plan["steps"]))
        self.assertTrue(all("uncertainty" in step for step in plan["steps"]))
        self.assertTrue(all("reasoning_trace" in step for step in plan["steps"]))
        self.assertIn("success_prob", plan["plan_simulation"])
        self.assertIn("failure_propagation", plan["plan_simulation"])
        self.assertIn("contradictions", plan["plan_simulation"])

    def test_build_plan_causality_only_flows_forward_to_true_dependents(self) -> None:
        plan = build_plan(
            "open https://example.com after inspect page https://example.com and then deploy artifact build/app.zip to prod",
            str(self.base),
        )

        browser_open = next(step for step in plan["steps"] if step["kind"] == "browser_open")
        browser_open_impacted = set(browser_open["failure_impact"]["blocks"]) | set(browser_open["failure_impact"]["degrades"])
        browser_dom_inspect = next(step for step in plan["steps"] if step["kind"] == "browser_dom_inspect")
        inspect_impacted = set(browser_dom_inspect["failure_impact"]["blocks"]) | set(browser_dom_inspect["failure_impact"]["degrades"])

        self.assertIn("post_action_verification", browser_open_impacted)
        self.assertNotIn("web_verify", browser_open_impacted)
        self.assertNotIn("web_fetch", browser_open_impacted)
        self.assertNotIn("browser_dom_inspect", browser_open_impacted)
        self.assertIn("browser_open", inspect_impacted)
        self.assertIn("cloud_deploy", inspect_impacted)

    def test_build_plan_tracks_failure_condition_targets_and_fallback_phase(self) -> None:
        plan = build_plan(
            "open https://example.com and if open fails inspect page https://example.com and show file src/main.py:10-20 and show branch main and show artifact build/app.zip",
            str(self.base),
        )

        self.assertTrue(plan["targets"]["file_ranges"])
        self.assertTrue(plan["targets"]["branches"])
        self.assertTrue(plan["targets"]["artifacts"])
        self.assertEqual(1.0, float(plan["target_coverage"]["coverage_ratio"]))
        self.assertGreaterEqual(int(plan["reasoning_trace"]["failure_condition_count"]), 1)
        phase_names = [phase["name"] for phase in plan["phases"]]
        self.assertIn("fallback", phase_names)

        conditional_steps = [step for step in plan["steps"] if step.get("conditional_execution_mode") == "on_failure"]
        self.assertTrue(conditional_steps)
        self.assertTrue(any(step["kind"] == "browser_dom_inspect" for step in conditional_steps))
        self.assertTrue(all(step.get("executes_on_failure_of") for step in conditional_steps))
        self.assertTrue(any(step["kind"] == "highway_dispatch" and "src/main.py" in str(step["target"]) and "10-20" in str(step["target"]) for step in plan["steps"]))
        self.assertTrue(any(step["kind"] == "highway_dispatch" and "show branch main" in str(step["target"]) for step in plan["steps"]))
        self.assertTrue(any(step["kind"] == "highway_dispatch" and "show artifact build/app.zip" in str(step["target"]) for step in plan["steps"]))

    def test_build_plan_tracks_success_condition_followup_phase(self) -> None:
        plan = build_plan(
            "inspect page https://example.com and if inspect page https://example.com verifies then open https://example.com",
            str(self.base),
        )

        self.assertGreaterEqual(int(plan["reasoning_trace"]["conditional_count"]), 1)
        phase_names = [phase["name"] for phase in plan["phases"]]
        self.assertIn("followup", phase_names)

        success_steps = [step for step in plan["steps"] if step.get("conditional_execution_mode") == "on_verified"]
        self.assertTrue(success_steps)
        self.assertTrue(any(step["kind"] == "browser_open" for step in success_steps))
        self.assertTrue(all(step.get("executes_on_verified_of") for step in success_steps))

    def test_smart_planner_status_and_assess_surface_latest_profile(self) -> None:
        assessed = smart_planner_assess("open https://example.com and click", str(self.base))
        derivation_assessed = self_derivation_assess("open https://example.com and click", str(self.base))
        status = smart_planner_status(str(self.base))
        derivation_status = self_derivation_status(str(self.base))

        self.assertTrue(assessed["ok"])
        self.assertIn("smart_planner", assessed)
        self.assertIn("plan_simulation", assessed)
        self.assertIn("self_critique", assessed)
        self.assertIn("expected_success", assessed)
        self.assertIn("self_derivation", assessed)
        self.assertIn("success_prob", assessed["plan_simulation"])
        self.assertIn("failure_propagation", assessed["plan_simulation"])
        self.assertTrue(derivation_assessed["ok"])
        self.assertIn("recommended_branch_id", derivation_assessed)
        self.assertGreaterEqual(int(derivation_assessed["self_derivation"]["generated_count"]), 10)
        self.assertTrue(status["ok"])
        self.assertEqual(assessed["smart_planner"]["strategy"], status["latest"]["strategy"])
        self.assertIn("planner_feedback_history_count", status)
        self.assertTrue(derivation_status["ok"])
        self.assertGreaterEqual(int(derivation_status["pattern_count"]), 1)


if __name__ == "__main__":
    unittest.main()
