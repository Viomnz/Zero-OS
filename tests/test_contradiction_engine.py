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
