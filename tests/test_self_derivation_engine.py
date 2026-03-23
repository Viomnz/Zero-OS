import json
import shutil
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from zero_os.self_derivation_engine import (
    _branch_shape_profile,
    _current_planner_version,
    _current_strategy_code_version,
    _strategy_canary_plan,
    _strategy_condition_profile,
    derive_interpretations,
    record_strategy_outcome,
    self_derivation_revalidate,
    self_derivation_status,
    survivor_generation_guidance,
    survivor_strategy_guidance,
)
from zero_os.task_planner import build_candidate_plans, build_plan


class SelfDerivationEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="self_derivation_engine_")
        self.base = Path(self.tempdir)
        (self.base / ".zero_os").mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_self_derivation_generates_diverse_interpretations_and_survivors(self) -> None:
        plan = build_plan(
            "open https://example.com after inspect page https://example.com and then deploy artifact build/app.zip to prod",
            str(self.base),
        )
        bundle = build_candidate_plans(
            "open https://example.com after inspect page https://example.com and then deploy artifact build/app.zip to prod",
            str(self.base),
            base_plan=plan,
        )

        report = derive_interpretations(str(self.base), plan["request"], plan, list(bundle["candidates"]))

        self.assertTrue(report["ok"])
        self.assertGreaterEqual(int(report["generated_count"]), 10)
        self.assertGreaterEqual(int(report["survivor_count"]), 1)
        self.assertTrue(report["top_survivors"])
        self.assertTrue(report["knowledge"])

    def test_self_derivation_status_exposes_pattern_memory(self) -> None:
        plan = build_plan("open https://example.com and click", str(self.base))
        bundle = build_candidate_plans("open https://example.com and click", str(self.base), base_plan=plan)
        derive_interpretations(str(self.base), plan["request"], plan, list(bundle["candidates"]))

        status = self_derivation_status(str(self.base))

        self.assertTrue(status["ok"])
        self.assertGreaterEqual(int(status["pattern_count"]), 1)
        self.assertGreaterEqual(int(status["knowledge_count"]), 1)
        self.assertGreaterEqual(int(status["validated_pattern_count"]), 1)
        self.assertTrue(Path(status["latest_path"]).exists())
        self.assertTrue(Path(status["memory_path"]).exists())

    def test_self_derivation_status_exposes_surface_freshness_profiles(self) -> None:
        issue_plan = build_plan("github issue read octo/test 12", str(self.base))
        pr_plan = build_plan("github pr read octo/test 34", str(self.base))

        record_strategy_outcome(
            str(self.base),
            issue_plan,
            {
                "ok": True,
                "results": [{"ok": True, "kind": "github_issue_read"}],
                "contradiction_gate": {"decision": "allow"},
                "replan": {"applied": False, "attempted": False},
            },
        )
        record_strategy_outcome(
            str(self.base),
            pr_plan,
            {
                "ok": True,
                "results": [{"ok": True, "kind": "github_pr_read"}],
                "contradiction_gate": {"decision": "allow"},
                "replan": {"applied": False, "attempted": False},
            },
        )

        status = self_derivation_status(str(self.base))
        surface_profiles = dict(status.get("surface_freshness_profiles") or {})

        self.assertIn("github_issue_read_surface", surface_profiles)
        self.assertIn("github_pr_read_surface", surface_profiles)
        self.assertGreaterEqual(int(surface_profiles["github_issue_read_surface"]["count"]), 1)
        self.assertGreaterEqual(int(surface_profiles["github_pr_read_surface"]["count"]), 1)
        self.assertGreater(float(surface_profiles["github_issue_read_surface"]["freshness_score"]), 0.0)
        self.assertGreater(float(surface_profiles["github_pr_read_surface"]["freshness_score"]), 0.0)

    def test_self_derivation_builds_cross_context_validation_for_reusable_patterns(self) -> None:
        first_request = "browser status"
        second_request = "browser status and inspect page https://example.com"

        first_plan = build_plan(first_request, str(self.base))
        first_bundle = build_candidate_plans(first_request, str(self.base), base_plan=first_plan)
        derive_interpretations(str(self.base), first_plan["request"], first_plan, list(first_bundle["candidates"]))

        second_plan = build_plan(second_request, str(self.base))
        second_bundle = build_candidate_plans(second_request, str(self.base), base_plan=second_plan)
        derive_interpretations(str(self.base), second_plan["request"], second_plan, list(second_bundle["candidates"]))

        memory = json.loads((self.base / ".zero_os" / "assistant" / "self_derivation" / "memory.json").read_text(encoding="utf-8"))
        self.assertTrue(any(int(dict(record).get("validated_context_count", 0) or 0) >= 2 for record in dict(memory.get("patterns") or {}).values()))
        self.assertTrue(any(float(dict(record).get("cross_context_score", 0.0) or 0.0) > 0.0 for record in dict(memory.get("patterns") or {}).values()))

    def test_survivor_generation_guidance_prefers_context_matching_patterns(self) -> None:
        derivation_dir = self.base / ".zero_os" / "assistant" / "self_derivation"
        derivation_dir.mkdir(parents=True, exist_ok=True)
        plan = build_plan("open https://example.com and click", str(self.base))
        derivation_memory = {
            "schema_version": 1,
            "patterns": {
                "mutate -> prepare -> verify": {
                    "pattern_signature": "mutate -> prepare -> verify",
                    "survival_count": 4,
                    "average_score": 88.0,
                    "contexts": ['{"goal": "mutate_resource", "shape": "mixed_target", "targets": ["actions", "urls"]}'],
                    "context_range": 1,
                    "failure_conditions": [],
                    "structure": "mutate -> prepare -> verify",
                    "source_branch_ids": ["historical_mutate_first"],
                },
                "verify -> prepare -> mutate": {
                    "pattern_signature": "verify -> prepare -> mutate",
                    "survival_count": 2,
                    "average_score": 61.0,
                    "contexts": ['{"goal": "observe_resource", "shape": "single_target", "targets": ["urls"]}'],
                    "context_range": 1,
                    "failure_conditions": [],
                    "structure": "verify -> prepare -> mutate",
                    "source_branch_ids": ["historical_verify_first"],
                },
            },
            "knowledge": [],
            "meta_rules": [],
        }
        (derivation_dir / "memory.json").write_text(json.dumps(derivation_memory, indent=2) + "\n", encoding="utf-8")

        guidance = survivor_generation_guidance(str(self.base), plan)

        self.assertTrue(guidance["ok"])
        self.assertTrue(guidance["history_ready"])
        self.assertTrue(guidance["recommended_patterns"])
        self.assertEqual("mutate -> prepare -> verify", guidance["recommended_patterns"][0]["pattern_signature"])
        self.assertGreater(float(guidance["recommended_patterns"][0]["context_match"]), 0.9)

    def test_derive_interpretations_uses_strategy_guidance_to_suppress_high_intensity_variants(self) -> None:
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
                    "strategy_outcomes": {},
                    "meta_rules": [],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        plan = build_plan("open https://example.com and click", str(self.base))
        bundle = build_candidate_plans("open https://example.com and click", str(self.base), base_plan=plan)

        report = derive_interpretations(str(self.base), plan["request"], plan, list(bundle["candidates"]))

        self.assertEqual("conservative", report["strategy_guidance"]["preferred_strategy"])
        self.assertEqual("low", report["strategy_guidance"]["preferred_mutation_intensity"])
        self.assertEqual(0, int(report["generated_intensity_counts"].get("high", 0) or 0))
        self.assertEqual(0, int(report["generated_intensity_counts"].get("extreme", 0) or 0))

    def test_record_strategy_outcome_feeds_back_into_strategy_guidance(self) -> None:
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
                    "strategy_outcomes": {},
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
        plan["smart_planner"]["strategy"] = "verification_first"
        plan["smart_planner"]["strategy_mode"] = "deliberate"

        feedback = record_strategy_outcome(
            str(self.base),
            plan,
            {
                "ok": False,
                "results": [{"ok": False, "kind": "browser_open", "reason": "network_unreachable"}],
                "contradiction_gate": {"decision": "allow"},
                "replan": {"applied": False, "attempted": False},
            },
        )
        guidance = survivor_strategy_guidance(str(self.base), plan)

        self.assertTrue(feedback["ok"])
        self.assertEqual("verification_first", feedback["strategy"])
        self.assertGreater(float(guidance["strategy_outcome_penalty"]), 0.0)
        self.assertEqual("safe", guidance["preferred_mode"])
        self.assertIn("extreme", guidance["suppressed_mutation_intensities"])
        self.assertEqual(1, int(self_derivation_status(str(self.base))["strategy_outcome_count"]))

    def test_record_strategy_outcome_stores_branch_shape_and_version_lineage(self) -> None:
        plan = build_plan("open https://example.com and click", str(self.base))

        feedback = record_strategy_outcome(
            str(self.base),
            plan,
            {
                "ok": True,
                "results": [{"ok": True, "kind": "browser_open"}],
                "contradiction_gate": {"decision": "allow"},
                "replan": {"applied": False, "attempted": False},
            },
        )

        record = dict(feedback["record"])
        self.assertTrue(feedback["ok"])
        self.assertEqual(plan["planner_version"], record["planner_version"])
        self.assertIn("self_derivation:", str(record["code_version"]))
        self.assertTrue(str(record["last_branch_shape_signature"]))
        self.assertIn(record["last_branch_shape_signature"], dict(record.get("shape_profiles") or {}))
        self.assertEqual(
            "verify -> prepare -> mutate",
            dict(dict(record.get("shape_profiles") or {}).get(record["last_branch_shape_signature"], {})).get("branch_shape", {}).get("pattern_signature", ""),
        )

    def test_self_derivation_quarantines_multi_generation_version_mismatched_strategy_memory(self) -> None:
        derivation_dir = self.base / ".zero_os" / "assistant" / "self_derivation"
        derivation_dir.mkdir(parents=True, exist_ok=True)
        (derivation_dir / "memory.json").write_text(
            json.dumps(
                {
                    "schema_version": 2,
                    "patterns": {},
                    "knowledge": [],
                    "strategy_outcomes": {
                        "verification_first": {
                            "strategy": "verification_first",
                            "planner_version": "2026.01.15",
                            "code_version": "planner:2026.01.15|self_derivation:2026.01.15",
                            "planner_version_history": ["2025.12.01", "2026.01.15"],
                            "code_version_history": ["planner:2025.12.01|self_derivation:2025.12.01", "planner:2026.01.15|self_derivation:2026.01.15"],
                            "run_count": 6,
                            "success_count": 5,
                            "failure_count": 1,
                            "recovery_count": 1,
                            "contradiction_hold_count": 0,
                            "reroute_count": 1,
                            "success_rate": 0.833,
                            "failure_rate": 0.167,
                            "recovery_rate": 0.167,
                            "contradiction_hold_rate": 0.0,
                            "average_outcome_quality": 0.88,
                            "resilience_score": 0.84,
                            "last_run_utc": "2025-06-01T00:00:00+00:00",
                            "last_outcome": {"ok": True},
                        }
                    },
                    "quarantined_strategy_outcomes": {},
                    "meta_rules": [],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        status = self_derivation_status(str(self.base))

        self.assertEqual(0, int(status["strategy_outcome_count"]))
        self.assertEqual(1, int(status["quarantined_strategy_count"]))

    def test_survivor_strategy_guidance_uses_condition_specific_freshness(self) -> None:
        derivation_dir = self.base / ".zero_os" / "assistant" / "self_derivation"
        derivation_dir.mkdir(parents=True, exist_ok=True)
        plan = build_plan("open https://example.com and click", str(self.base))
        condition_profile = _strategy_condition_profile(plan)
        (derivation_dir / "memory.json").write_text(
            json.dumps(
                {
                    "schema_version": 2,
                    "patterns": {},
                    "knowledge": [],
                    "strategy_outcomes": {
                        "verification_first": {
                            "strategy": "verification_first",
                            "planner_version": _current_planner_version(),
                            "code_version": _current_strategy_code_version(),
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
                            "last_run_utc": "2025-06-01T00:00:00+00:00",
                            "condition_profiles": {
                                condition_profile["signature"]: {
                                    "condition_profile": {key: value for key, value in condition_profile.items() if key != "signature"},
                                    "run_count": 2,
                                    "success_count": 2,
                                    "failure_count": 0,
                                    "recovery_count": 0,
                                    "success_rate": 1.0,
                                    "failure_rate": 0.0,
                                    "recovery_rate": 0.0,
                                    "last_seen_utc": datetime.now(timezone.utc).isoformat(),
                                    "planner_version": _current_planner_version(),
                                    "code_version": _current_strategy_code_version(),
                                }
                            },
                            "last_outcome": {"ok": True},
                        }
                    },
                    "quarantined_strategy_outcomes": {},
                    "meta_rules": [],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        guidance = survivor_strategy_guidance(str(self.base), plan)

        self.assertTrue(guidance["outcome_guided"])
        self.assertGreater(float(guidance["strategy_outcome_summary"].get("freshness_score", 0.0) or 0.0), 0.7)
        self.assertTrue(guidance["strategy_outcome_summary"].get("condition_match_exact", False))

    def test_strategy_condition_profile_splits_browser_and_github_surfaces(self) -> None:
        browser_read = build_plan("browser status", str(self.base))
        browser_mutate = build_plan("open https://example.com and click", str(self.base))

        github_read = {
            "request": "github issue read octocat/Hello-World 1",
            "steps": [{"kind": "github_issue_read", "target": {"repo": "octocat/Hello-World", "issue": 1}}],
            "request_targets": {"items": [{"id": "issue", "type": "github_issues", "value": {"repo": "octocat/Hello-World", "issue": 1}}]},
            "request_decomposition": [],
            "risk_level": "low",
            "execution_mode": "safe",
            "smart_planner": {"strategy_mode": "safe"},
        }
        github_reply = {
            "request": "github issue reply post octocat/Hello-World 1",
            "steps": [{"kind": "github_issue_reply_post", "target": {"repo": "octocat/Hello-World", "issue": 1, "body": "hi"}}],
            "request_targets": {"items": [{"id": "issue", "type": "github_issues", "value": {"repo": "octocat/Hello-World", "issue": 1}}]},
            "request_decomposition": [],
            "risk_level": "medium",
            "execution_mode": "safe",
            "smart_planner": {"strategy_mode": "safe"},
        }

        self.assertEqual("browser_read_surface", _strategy_condition_profile(browser_read)["subsystem_surface"])
        self.assertEqual("browser_click_surface", _strategy_condition_profile(browser_mutate)["subsystem_surface"])
        self.assertEqual("github_issue_read_surface", _strategy_condition_profile(github_read)["subsystem_surface"])
        self.assertEqual("github_issue_reply_post_surface", _strategy_condition_profile(github_reply)["subsystem_surface"])

    def test_strategy_condition_profile_splits_deploy_verify_and_mutate_surfaces(self) -> None:
        deploy_verify = {
            "request": "configure cloud target staging",
            "steps": [{"kind": "cloud_target_set", "target": {"target": "staging"}}],
            "request_targets": {"items": [{"id": "target", "type": "cloud_targets", "value": {"target": "staging"}}]},
            "request_decomposition": [],
            "risk_level": "low",
            "execution_mode": "safe",
            "smart_planner": {"strategy_mode": "safe"},
        }
        deploy_mutate = {
            "request": "deploy artifact build/canary.zip to staging",
            "steps": [
                {"kind": "cloud_target_set", "target": {"target": "staging"}},
                {"kind": "cloud_deploy", "target": {"target": "staging", "artifact": "build/canary.zip"}},
            ],
            "request_targets": {
                "items": [
                    {"id": "target", "type": "cloud_targets", "value": {"target": "staging"}},
                    {"id": "deploy", "type": "deployments", "value": {"target": "staging", "artifact": "build/canary.zip"}},
                ]
            },
            "request_decomposition": [],
            "risk_level": "medium",
            "execution_mode": "safe",
            "smart_planner": {"strategy_mode": "safe"},
        }

        self.assertEqual("deploy_verify_surface", _strategy_condition_profile(deploy_verify)["subsystem_surface"])
        self.assertEqual("deploy_mutate_surface", _strategy_condition_profile(deploy_mutate)["subsystem_surface"])

    def test_strategy_condition_profile_splits_browser_click_and_input_surfaces(self) -> None:
        click_plan = {
            "request": "open https://example.com and click",
            "steps": [{"kind": "browser_action", "target": {"url": "https://example.com", "action": "click", "selector": "body"}}],
            "request_targets": {"items": [{"type": "urls", "value": "https://example.com"}]},
            "request_decomposition": [],
            "risk_level": "medium",
            "execution_mode": "safe",
            "smart_planner": {"strategy_mode": "safe"},
        }
        input_plan = {
            "request": "open https://example.com and input hello",
            "steps": [{"kind": "browser_action", "target": {"url": "https://example.com", "action": "input", "selector": "body", "value": "hello"}}],
            "request_targets": {"items": [{"type": "urls", "value": "https://example.com"}]},
            "request_decomposition": [],
            "risk_level": "medium",
            "execution_mode": "safe",
            "smart_planner": {"strategy_mode": "safe"},
        }

        self.assertEqual("browser_click_surface", _strategy_condition_profile(click_plan)["subsystem_surface"])
        self.assertEqual("browser_input_surface", _strategy_condition_profile(input_plan)["subsystem_surface"])

    def test_strategy_condition_profile_splits_github_reply_draft_and_post_surfaces(self) -> None:
        draft_plan = {
            "request": "draft github reply",
            "steps": [{"kind": "github_issue_reply_draft", "target": {"repo": "octocat/Hello-World", "issue": 1}}],
            "request_targets": {"items": [{"type": "github_issues", "value": {"repo": "octocat/Hello-World", "issue": 1}}]},
            "request_decomposition": [],
            "risk_level": "medium",
            "execution_mode": "safe",
            "smart_planner": {"strategy_mode": "safe"},
        }
        post_plan = {
            "request": "post github reply",
            "steps": [{"kind": "github_issue_reply_post", "target": {"repo": "octocat/Hello-World", "issue": 1}}],
            "request_targets": {"items": [{"type": "github_issues", "value": {"repo": "octocat/Hello-World", "issue": 1}}]},
            "request_decomposition": [],
            "risk_level": "medium",
            "execution_mode": "safe",
            "smart_planner": {"strategy_mode": "safe"},
        }

        self.assertEqual("github_issue_reply_draft_surface", _strategy_condition_profile(draft_plan)["subsystem_surface"])
        self.assertEqual("github_issue_reply_post_surface", _strategy_condition_profile(post_plan)["subsystem_surface"])

    def test_strategy_condition_profile_splits_browser_submit_surface(self) -> None:
        submit_plan = {
            "request": "open https://example.com and submit",
            "steps": [{"kind": "browser_action", "target": {"url": "https://example.com", "action": "submit", "selector": "body"}}],
            "request_targets": {"items": [{"type": "urls", "value": "https://example.com"}]},
            "request_decomposition": [],
            "risk_level": "medium",
            "execution_mode": "safe",
            "smart_planner": {"strategy_mode": "safe"},
        }

        self.assertEqual("browser_submit_surface", _strategy_condition_profile(submit_plan)["subsystem_surface"])

    def test_strategy_condition_profile_splits_github_issue_and_pr_reply_surfaces(self) -> None:
        issue_reply = {
            "request": "post github issue reply",
            "steps": [{"kind": "github_issue_reply_post", "target": {"repo": "octocat/Hello-World", "issue": 1}}],
            "request_targets": {"items": [{"type": "github_issues", "value": {"repo": "octocat/Hello-World", "issue": 1}}]},
            "request_decomposition": [],
            "risk_level": "medium",
            "execution_mode": "safe",
            "smart_planner": {"strategy_mode": "safe"},
        }
        pr_reply = {
            "request": "post github pr reply",
            "steps": [{"kind": "github_pr_reply_post", "target": {"repo": "octocat/Hello-World", "pr": 1}}],
            "request_targets": {"items": [{"type": "github_prs", "value": {"repo": "octocat/Hello-World", "pr": 1}}]},
            "request_decomposition": [],
            "risk_level": "medium",
            "execution_mode": "safe",
            "smart_planner": {"strategy_mode": "safe"},
        }

        self.assertEqual("github_issue_reply_post_surface", _strategy_condition_profile(issue_reply)["subsystem_surface"])
        self.assertEqual("github_pr_reply_post_surface", _strategy_condition_profile(pr_reply)["subsystem_surface"])

    def test_strategy_condition_profile_splits_github_read_comment_and_plan_surfaces(self) -> None:
        issue_read = {
            "request": "read github issue",
            "steps": [{"kind": "github_issue_read", "target": {"repo": "octocat/Hello-World", "issue": 1}}],
            "request_targets": {"items": [{"type": "github_issues", "value": {"repo": "octocat/Hello-World", "issue": 1}}]},
            "request_decomposition": [],
            "risk_level": "low",
            "execution_mode": "safe",
            "smart_planner": {"strategy_mode": "safe"},
        }
        issue_comments = {
            "request": "comment history for github issue",
            "steps": [{"kind": "github_issue_comments", "target": {"repo": "octocat/Hello-World", "issue": 1}}],
            "request_targets": {"items": [{"type": "github_issues", "value": {"repo": "octocat/Hello-World", "issue": 1}}]},
            "request_decomposition": [],
            "risk_level": "low",
            "execution_mode": "safe",
            "smart_planner": {"strategy_mode": "safe"},
        }
        issue_plan = {
            "request": "plan github issue",
            "steps": [{"kind": "github_issue_plan", "target": {"repo": "octocat/Hello-World", "issue": 1}}],
            "request_targets": {"items": [{"type": "github_issues", "value": {"repo": "octocat/Hello-World", "issue": 1}}]},
            "request_decomposition": [],
            "risk_level": "low",
            "execution_mode": "safe",
            "smart_planner": {"strategy_mode": "safe"},
        }
        pr_read = {
            "request": "read github pr",
            "steps": [{"kind": "github_pr_read", "target": {"repo": "octocat/Hello-World", "pr": 1}}],
            "request_targets": {"items": [{"type": "github_prs", "value": {"repo": "octocat/Hello-World", "pr": 1}}]},
            "request_decomposition": [],
            "risk_level": "low",
            "execution_mode": "safe",
            "smart_planner": {"strategy_mode": "safe"},
        }
        pr_comments = {
            "request": "comment history for github pr",
            "steps": [{"kind": "github_pr_comments", "target": {"repo": "octocat/Hello-World", "pr": 1}}],
            "request_targets": {"items": [{"type": "github_prs", "value": {"repo": "octocat/Hello-World", "pr": 1}}]},
            "request_decomposition": [],
            "risk_level": "low",
            "execution_mode": "safe",
            "smart_planner": {"strategy_mode": "safe"},
        }
        pr_plan = {
            "request": "plan github pr",
            "steps": [{"kind": "github_pr_plan", "target": {"repo": "octocat/Hello-World", "pr": 1}}],
            "request_targets": {"items": [{"type": "github_prs", "value": {"repo": "octocat/Hello-World", "pr": 1}}]},
            "request_decomposition": [],
            "risk_level": "low",
            "execution_mode": "safe",
            "smart_planner": {"strategy_mode": "safe"},
        }

        self.assertEqual("github_issue_read_surface", _strategy_condition_profile(issue_read)["subsystem_surface"])
        self.assertEqual("github_issue_comment_surface", _strategy_condition_profile(issue_comments)["subsystem_surface"])
        self.assertEqual("github_issue_plan_surface", _strategy_condition_profile(issue_plan)["subsystem_surface"])
        self.assertEqual("github_pr_read_surface", _strategy_condition_profile(pr_read)["subsystem_surface"])
        self.assertEqual("github_pr_comment_surface", _strategy_condition_profile(pr_comments)["subsystem_surface"])
        self.assertEqual("github_pr_plan_surface", _strategy_condition_profile(pr_plan)["subsystem_surface"])

    def test_self_derivation_revalidate_restores_ready_quarantined_strategy(self) -> None:
        derivation_dir = self.base / ".zero_os" / "assistant" / "self_derivation"
        derivation_dir.mkdir(parents=True, exist_ok=True)
        seed_record = {
            "strategy": "verification_first",
            "planner_version": _current_planner_version(),
            "code_version": _current_strategy_code_version(),
            "planner_version_history": [_current_planner_version()],
            "code_version_history": [_current_strategy_code_version()],
            "run_count": 5,
            "success_count": 4,
            "failure_count": 1,
            "recovery_count": 1,
            "contradiction_hold_count": 0,
            "reroute_count": 1,
            "success_rate": 0.8,
            "failure_rate": 0.2,
            "recovery_rate": 0.2,
            "contradiction_hold_rate": 0.0,
            "average_outcome_quality": 0.86,
            "resilience_score": 0.82,
            "last_run_utc": datetime.now(timezone.utc).isoformat(),
            "last_branch_shape": {"pattern_signature": "verify -> prepare -> mutate"},
            "last_condition_profile": {
                "subsystem_surface": "browser_mutate_surface",
                "structure_family": "interactive_browser_flow",
                "semantic_goal": "mutate_resource",
                "target_families": ["interaction_surface", "remote_source"],
                "target_types": ["urls"],
                "risk_level": "medium",
                "execution_mode": "safe",
                "strategy_mode": "safe",
            },
            "last_outcome": {"ok": True},
        }
        canary_plan = _strategy_canary_plan("verification_first", seed_record)
        canary_condition = _strategy_condition_profile(canary_plan)
        canary_shape = _branch_shape_profile(canary_plan)
        seed_record["condition_profiles"] = {
            canary_condition["signature"]: {
                "condition_profile": {key: value for key, value in canary_condition.items() if key != "signature"},
                "run_count": 2,
                "success_count": 2,
                "failure_count": 0,
                "recovery_count": 0,
                "success_rate": 1.0,
                "failure_rate": 0.0,
                "recovery_rate": 0.0,
                "last_seen_utc": datetime.now(timezone.utc).isoformat(),
                "planner_version": _current_planner_version(),
                "code_version": _current_strategy_code_version(),
            }
        }
        seed_record["shape_profiles"] = {
            canary_shape["signature"]: {
                "branch_shape": {key: value for key, value in canary_shape.items() if key != "signature"},
                "run_count": 2,
                "success_count": 2,
                "failure_count": 0,
                "recovery_count": 0,
                "success_rate": 1.0,
                "failure_rate": 0.0,
                "recovery_rate": 0.0,
                "average_outcome_quality": 0.9,
                "last_seen_utc": datetime.now(timezone.utc).isoformat(),
                "planner_version": _current_planner_version(),
                "code_version": _current_strategy_code_version(),
            }
        }
        (derivation_dir / "memory.json").write_text(
            json.dumps(
                {
                    "schema_version": 2,
                    "patterns": {},
                    "knowledge": [],
                    "strategy_outcomes": {},
                    "quarantined_strategy_outcomes": {"verification_first": seed_record},
                    "meta_rules": [],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        result = self_derivation_revalidate(str(self.base))
        status = self_derivation_status(str(self.base))

        self.assertTrue(result["ok"])
        self.assertEqual(1, result["restored_count"])
        self.assertEqual(0, result["remaining_quarantined_count"])
        self.assertEqual(1, status["strategy_outcome_count"])
        self.assertEqual(0, status["quarantined_strategy_count"])


if __name__ == "__main__":
    unittest.main()
