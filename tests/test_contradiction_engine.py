import json
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

from zero_os.contradiction_engine import contradiction_engine_status, review_branch, review_run, select_stable_branch
from zero_os.world_model import build_world_model, persist_world_model


class ContradictionEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_contradiction_engine_")
        self.base = Path(self.tempdir)

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_review_run_allows_stable_status_branch(self) -> None:
        review = review_run(
            str(self.base),
            "check system status",
            {
                "intent": {"intent": "status"},
                "steps": [{"kind": "system_status", "target": "health"}],
            },
            [{"ok": True, "kind": "system_status", "result": {"ok": True}}],
            run_ok=True,
        )

        self.assertEqual("allow", review["decision"])
        self.assertEqual(0, review["contradiction_count"])
        self.assertGreaterEqual(len(review["stable_claims"]), 1)

    def test_review_run_holds_when_self_contradiction_is_active(self) -> None:
        runtime_dir = self.base / ".zero_os" / "runtime"
        runtime_dir.mkdir(parents=True, exist_ok=True)
        (runtime_dir / "zero_ai_self_continuity.json").write_text(
            json.dumps(
                {
                    "continuity": {"same_system": True, "continuity_score": 82.0},
                    "contradiction_detection": {
                        "has_contradiction": True,
                        "issues": ["identity_missing_anti_contradiction_constraint"],
                    },
                    "policy_memory": {"contradiction_event_count": 1},
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        review = review_run(
            str(self.base),
            "check system status",
            {
                "intent": {"intent": "status"},
                "steps": [{"kind": "system_status", "target": "health"}],
            },
            [{"ok": True, "kind": "system_status", "result": {"ok": True}}],
            run_ok=True,
        )

        self.assertEqual("hold", review["decision"])
        self.assertGreater(review["contradiction_count"], 0)
        self.assertIn("Resolve self contradictions", review["recommended_action"])

    def test_status_reflects_latest_review(self) -> None:
        review_run(
            str(self.base),
            "check system status",
            {
                "intent": {"intent": "status"},
                "steps": [{"kind": "system_status", "target": "health"}],
            },
            [{"ok": True, "kind": "system_status", "result": {"ok": True}}],
            run_ok=True,
        )

        status = contradiction_engine_status(str(self.base))

        self.assertTrue(status["ok"])
        self.assertEqual("allow", status["last_decision"])
        self.assertEqual(0, status["last_contradiction_count"])
        self.assertTrue(Path(status["path"]).exists())

    def test_review_branch_holds_mutating_status_candidate_before_execution(self) -> None:
        review = review_branch(
            str(self.base),
            "check system status",
            {
                "intent": {"intent": "status", "goals": ["check system status"]},
                "branch": {"id": "primary", "source": "direct_plan", "note": "unstable", "preferred": True},
                "steps": [
                    {"kind": "system_status", "target": "health"},
                    {"kind": "recover", "target": "runtime"},
                ],
            },
        )

        self.assertEqual("hold", review["decision"])
        self.assertEqual("branch", review["mode"])
        self.assertGreater(review["contradiction_count"], 0)
        self.assertIn("read-only request", review["issues"][0]["message"].lower())

    def test_review_branch_holds_when_world_model_has_pending_approvals_for_mutation(self) -> None:
        model = build_world_model(
            str(self.base),
            sources={
                "runtime": {"runtime_ready": True, "missing": False, "runtime_score": 100.0},
                "runtime_loop": {"enabled": True},
                "runtime_agent": {"installed": True, "running": True},
                "continuity": {
                    "continuity": {"same_system": True, "continuity_score": 100.0},
                    "contradiction_detection": {"has_contradiction": False},
                },
                "pressure": {"missing": False, "overall_score": 100.0},
                "approvals": {"pending_count": 1},
                "jobs": {"count": 0},
            },
        )
        persist_world_model(str(self.base), model, flush=True)

        review = review_branch(
            str(self.base),
            "open https://example.com and click",
            {
                "intent": {"intent": "web", "goals": ["open https://example.com and click"]},
                "branch": {"id": "primary", "source": "direct_plan", "note": "mutating", "preferred": True},
                "steps": [
                    {"kind": "browser_open", "target": "https://example.com"},
                    {"kind": "browser_action", "target": {"action": "click", "selector": "#go"}},
                ],
            },
        )

        codes = {issue["code"] for issue in review["issues"]}
        self.assertEqual("hold", review["decision"])
        self.assertIn("world_model_approval_block", codes)

    def test_review_branch_holds_code_change_when_scope_is_not_ready(self) -> None:
        review = review_branch(
            str(self.base),
            'replace "a" with "b" in README.md',
            {
                "intent": {"intent": "code", "goals": ['replace "a" with "b" in README.md']},
                "branch": {"id": "primary", "source": "direct_plan", "note": "code", "preferred": True},
                "code_workbench_context": {
                    "scope_ready": False,
                    "verification_ready": False,
                    "out_of_scope_count": 1,
                    "out_of_scope_files": ["README.md"],
                    "missing_in_scope_files": [],
                },
                "steps": [
                    {
                        "kind": "code_change",
                        "target": {"files": ["README.md"], "instruction": {"operation": "replace", "old": "a", "new": "b"}},
                    }
                ],
            },
        )

        codes = {issue["code"] for issue in review["issues"]}
        self.assertEqual("hold", review["decision"])
        self.assertIn("code_scope_not_ready", codes)

    def test_select_stable_branch_discards_conflicting_recovery_branch(self) -> None:
        with patch(
            "zero_os.contradiction_engine._workflow_signals",
            return_value={
                "runtime": {"runtime_ready": True},
                "workflows": {
                    "lanes": {
                        "recovery": {"ready": True, "active": True},
                        "self_repair": {"ready": True, "active": True},
                    }
                },
            },
        ):
            selection = select_stable_branch(
                str(self.base),
                "recover system and self repair runtime",
                [
                    {
                        "intent": {"intent": "recover", "goals": ["recover system and self repair runtime"]},
                        "branch": {"id": "primary", "source": "direct_plan", "note": "conflicting", "preferred": True},
                        "steps": [
                            {"kind": "self_repair", "target": "runtime"},
                            {"kind": "recover", "target": "runtime"},
                            {"kind": "autonomy_gate", "target": "recover system and self repair runtime"},
                        ],
                    },
                    {
                        "intent": {"intent": "recover", "goals": ["recover system and self repair runtime"]},
                        "branch": {"id": "single_recover", "source": "regenerated_single_remediation", "note": "recover only", "preferred": True},
                        "steps": [
                            {"kind": "recover", "target": "runtime"},
                            {"kind": "autonomy_gate", "target": "recover system and self repair runtime"},
                        ],
                    },
                ],
            )

        self.assertTrue(selection["ok"])
        self.assertIsNotNone(selection["selected_branch"])
        self.assertEqual("single_recover", selection["selected_branch"]["branch"]["id"])
        self.assertGreaterEqual(selection["discarded_count"], 1)

    def test_select_stable_branch_prefers_higher_evidence_weight(self) -> None:
        selection = select_stable_branch(
            str(self.base),
            "check system status",
            [
                {
                    "intent": {"intent": "status", "goals": ["check system status"]},
                    "branch": {"id": "low_evidence", "source": "direct_plan", "note": "low", "preferred": False},
                    "steps": [{"kind": "system_status", "target": "health"}],
                    "evidence": {"total_weight": 0.35, "memory_weight": 0.1, "core_law_weight": 1.0},
                },
                {
                    "intent": {"intent": "status", "goals": ["check system status"]},
                    "branch": {"id": "high_evidence", "source": "memory_weighted", "note": "high", "preferred": False},
                    "steps": [{"kind": "system_status", "target": "health"}],
                    "evidence": {"total_weight": 0.95, "memory_weight": 0.8, "core_law_weight": 1.0},
                },
            ],
        )

        self.assertEqual("high_evidence", selection["selected_branch"]["branch"]["id"])

    def test_select_stable_branch_prefers_higher_planner_confidence_when_other_scores_match(self) -> None:
        selection = select_stable_branch(
            str(self.base),
            "check https://example.com",
            [
                {
                    "intent": {"intent": "web", "goals": ["check https://example.com"]},
                    "branch": {"id": "low_confidence", "source": "direct_plan", "note": "low", "preferred": False},
                    "planner_confidence": 0.42,
                    "risk_level": "medium",
                    "steps": [{"kind": "web_verify", "target": "https://example.com"}],
                    "evidence": {"total_weight": 0.9, "memory_weight": 0.4, "core_law_weight": 1.0},
                },
                {
                    "intent": {"intent": "web", "goals": ["check https://example.com"]},
                    "branch": {"id": "high_confidence", "source": "direct_plan", "note": "high", "preferred": False},
                    "planner_confidence": 0.93,
                    "risk_level": "low",
                    "steps": [{"kind": "web_verify", "target": "https://example.com"}],
                    "evidence": {"total_weight": 0.9, "memory_weight": 0.4, "core_law_weight": 1.0},
                },
            ],
        )

        self.assertEqual("high_confidence", selection["selected_branch"]["branch"]["id"])

    def test_select_stable_branch_prefers_full_target_coverage_for_web_requests(self) -> None:
        selection = select_stable_branch(
            str(self.base),
            "open https://example.com and click #go",
            [
                {
                    "intent": {"intent": "web", "goals": ["open https://example.com and click #go"]},
                    "branch": {"id": "partial_coverage", "source": "direct_plan", "note": "partial", "preferred": False},
                    "planner_confidence": 0.88,
                    "risk_level": "medium",
                    "steps": [{"kind": "web_verify", "target": "https://example.com"}],
                    "target_coverage": {
                        "covered_target_ids": ["target_url"],
                        "unbound_target_ids": ["target_action"],
                        "coverage_ratio": 0.5,
                    },
                    "evidence": {"total_weight": 0.9, "memory_weight": 0.4, "core_law_weight": 1.0},
                },
                {
                    "intent": {"intent": "web", "goals": ["open https://example.com and click #go"]},
                    "branch": {"id": "full_coverage", "source": "direct_plan", "note": "full", "preferred": False},
                    "planner_confidence": 0.88,
                    "risk_level": "medium",
                    "steps": [
                        {"kind": "web_verify", "target": "https://example.com"},
                        {"kind": "browser_action", "target": {"url": "https://example.com", "action": "click", "selector": "#go"}},
                    ],
                    "target_coverage": {
                        "covered_target_ids": ["target_url", "target_action"],
                        "unbound_target_ids": [],
                        "coverage_ratio": 1.0,
                    },
                    "evidence": {"total_weight": 0.9, "memory_weight": 0.4, "core_law_weight": 1.0},
                },
            ],
        )

        self.assertEqual("full_coverage", selection["selected_branch"]["branch"]["id"])

    def test_select_stable_branch_prefers_survivor_history_when_other_scores_match(self) -> None:
        derivation_dir = self.base / ".zero_os" / "assistant" / "self_derivation"
        derivation_dir.mkdir(parents=True, exist_ok=True)
        (derivation_dir / "memory.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "patterns": {
                        "verify": {
                            "pattern_signature": "verify",
                            "survival_count": 1,
                            "average_score": 35.0,
                            "contexts": [],
                            "context_range": 0,
                            "failure_conditions": [],
                            "structure": "verify",
                            "source_branch_ids": ["low_history"],
                        },
                        "verify -> prepare": {
                            "pattern_signature": "verify -> prepare",
                            "survival_count": 4,
                            "average_score": 82.0,
                            "contexts": [],
                            "context_range": 0,
                            "failure_conditions": [],
                            "structure": "verify -> prepare",
                            "source_branch_ids": ["high_history"],
                        },
                    },
                    "knowledge": [],
                    "meta_rules": [],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        selection = select_stable_branch(
            str(self.base),
            "open https://example.com",
            [
                {
                    "intent": {"intent": "web", "goals": ["open https://example.com"]},
                    "branch": {"id": "low_history", "source": "direct_plan", "note": "low", "preferred": False},
                    "planner_confidence": 0.88,
                    "risk_level": "medium",
                    "execution_mode": "deliberate",
                    "steps": [{"kind": "web_verify", "target": "https://example.com"}],
                    "evidence": {"total_weight": 0.9, "memory_weight": 0.4, "core_law_weight": 1.0},
                },
                {
                    "intent": {"intent": "web", "goals": ["open https://example.com"]},
                    "branch": {"id": "high_history", "source": "direct_plan", "note": "high", "preferred": False},
                    "planner_confidence": 0.88,
                    "risk_level": "medium",
                    "execution_mode": "deliberate",
                    "steps": [
                        {"kind": "web_verify", "target": "https://example.com"},
                        {"kind": "browser_open", "target": "https://example.com"},
                    ],
                    "evidence": {"total_weight": 0.9, "memory_weight": 0.4, "core_law_weight": 1.0},
                },
            ],
        )

        self.assertEqual("high_history", selection["selected_branch"]["branch"]["id"])

    def test_select_stable_branch_prefers_recent_proven_strategy_over_unsafe_strategy(self) -> None:
        derivation_dir = self.base / ".zero_os" / "assistant" / "self_derivation"
        derivation_dir.mkdir(parents=True, exist_ok=True)
        (derivation_dir / "memory.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "patterns": {},
                    "knowledge": [],
                    "strategy_outcomes": {
                        "dependency_aware": {
                            "strategy": "dependency_aware",
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
                            "average_outcome_quality": 0.92,
                            "resilience_score": 0.9,
                            "first_run_utc": "2026-03-21T00:00:00+00:00",
                            "last_run_utc": "2026-03-21T00:00:00+00:00",
                            "last_outcome": {"ok": True},
                        },
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
                            "first_run_utc": "2026-03-21T00:00:00+00:00",
                            "last_run_utc": "2026-03-21T00:00:00+00:00",
                            "last_outcome": {"ok": False},
                        },
                    },
                    "meta_rules": [],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        selection = select_stable_branch(
            str(self.base),
            "open https://example.com",
            [
                {
                    "request": "open https://example.com",
                    "request_targets": {"items": [{"id": "urls_0", "type": "urls", "value": "https://example.com"}]},
                    "request_decomposition": [
                        {"id": "subgoal_0", "depends_on": [], "conditional": False},
                        {"id": "subgoal_1", "depends_on": ["subgoal_0"], "conditional": False},
                    ],
                    "intent": {"intent": "web", "goals": ["open https://example.com"]},
                    "branch": {"id": "dependency_recent", "source": "direct_plan", "note": "dependency", "preferred": False},
                    "planner_confidence": 0.88,
                    "risk_level": "medium",
                    "execution_mode": "deliberate",
                    "steps": [
                        {"kind": "web_verify", "target": "https://example.com", "subgoal_id": "subgoal_0"},
                        {"kind": "browser_open", "target": "https://example.com", "subgoal_id": "subgoal_1"},
                    ],
                    "evidence": {"total_weight": 0.9, "memory_weight": 0.4, "core_law_weight": 1.0},
                },
                {
                    "request": "open https://example.com",
                    "request_targets": {"items": [{"id": "urls_0", "type": "urls", "value": "https://example.com"}, {"id": "actions_0", "type": "actions", "value": "open"}]},
                    "request_decomposition": [{"id": "subgoal_0", "depends_on": [], "conditional": False}],
                    "intent": {"intent": "web", "goals": ["open https://example.com"]},
                    "branch": {"id": "verify_unsafe", "source": "direct_plan", "note": "unsafe", "preferred": False},
                    "planner_confidence": 0.88,
                    "risk_level": "medium",
                    "execution_mode": "deliberate",
                    "steps": [
                        {"kind": "web_verify", "target": "https://example.com", "subgoal_id": "subgoal_0"},
                        {"kind": "browser_open", "target": "https://example.com", "subgoal_id": "subgoal_0"},
                    ],
                    "evidence": {"total_weight": 0.9, "memory_weight": 0.4, "core_law_weight": 1.0},
                },
            ],
        )

        self.assertEqual("dependency_recent", selection["selected_branch"]["branch"]["id"])
        self.assertEqual("proven", selection["selected_branch"]["strategy_guidance"]["recovery_profile"])
        self.assertEqual("fragile_and_unsafe", selection["discarded_branches"][0]["strategy_guidance"]["recovery_profile"])

    @patch(
        "zero_os.contradiction_engine._workflow_signals",
        return_value={
            "runtime": {"runtime_ready": True},
            "workflows": {"lanes": {"self_repair": {"ready": False, "active": False}}},
        },
    )
    def test_review_branch_holds_when_typed_workflow_lane_is_not_ready(self, _mock_workflow) -> None:
        review = review_branch(
            str(self.base),
            "self repair runtime",
            {
                "intent": {"intent": "self_repair", "goals": ["self repair runtime"]},
                "steps": [{"kind": "self_repair", "target": "runtime"}],
            },
        )

        self.assertEqual("hold", review["decision"])
        self.assertIn("typed_workflow_not_ready", {issue["code"] for issue in review["issues"]})

    @patch(
        "zero_os.contradiction_engine._workflow_signals",
        return_value={
            "runtime": {"runtime_ready": True},
            "workflows": {
                "lanes": {
                    "self_repair": {
                        "ready": False,
                        "active": True,
                        "raw_action_policy": {"decision": "approval_required"},
                    }
                }
            },
        },
    )
    def test_review_branch_allows_approval_backed_self_repair_lane_to_continue(self, _mock_workflow) -> None:
        review = review_branch(
            str(self.base),
            "self repair runtime",
            {
                "intent": {"intent": "self_repair", "goals": ["self repair runtime"]},
                "branch": {"id": "primary", "source": "direct_plan", "note": "approval-backed", "preferred": True},
                "steps": [{"kind": "self_repair", "target": "runtime"}],
            },
        )

        self.assertEqual("allow", review["decision"])
        issue = next(item for item in review["issues"] if item["code"] == "typed_workflow_not_ready")
        self.assertFalse(issue["blocking"])
        self.assertTrue(issue["details"]["approval_backed_remediation"])

    @patch(
        "zero_os.contradiction_engine._evolution_signals",
        return_value={
            "bounded": {"self_evolution_ready": True, "blocked_reasons": []},
            "source": {
                "source_evolution_ready": False,
                "proposal": {"blocked_reasons": ["bounded evolution safety preconditions are not satisfied"]},
            },
        },
    )
    def test_review_branch_holds_when_source_evolution_is_not_ready(self, _mock_evolution) -> None:
        review = review_branch(
            str(self.base),
            "align source defaults",
            {
                "intent": {"intent": "reasoning", "goals": ["align source defaults"]},
                "steps": [{"kind": "source_evolution_auto_run", "target": "defaults"}],
            },
        )

        self.assertEqual("hold", review["decision"])
        self.assertIn("source_evolution_not_ready", {issue["code"] for issue in review["issues"]})

    @patch(
        "zero_os.contradiction_engine._workflow_signals",
        return_value={
            "runtime": {"runtime_ready": True},
            "workflows": {"lanes": {"recovery": {"ready": True, "active": True}}},
        },
    )
    def test_review_branch_holds_when_high_risk_plan_has_low_planner_confidence(self, _mock_workflow) -> None:
        review = review_branch(
            str(self.base),
            "recover system",
            {
                "intent": {"intent": "recover", "goals": ["recover system"]},
                "planner_confidence": 0.42,
                "risk_level": "high",
                "steps": [{"kind": "recover", "target": "runtime"}],
            },
        )

        self.assertEqual("hold", review["decision"])
        self.assertIn("planner_confidence_below_high_risk_threshold", {issue["code"] for issue in review["issues"]})


if __name__ == "__main__":
    unittest.main()
