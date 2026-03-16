import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ai_from_scratch.internal_zero_reasoner import InternalReasoningResult
from ai_from_scratch.distributed_intelligence import run_distributed_reasoning


class DistributedIntelligenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_distributed_")
        self.base = Path(self.tempdir)

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def _gate(self, accepted: bool, output: str = "candidate") -> InternalReasoningResult:
        return InternalReasoningResult(
            accepted=accepted,
            output=output,
            attempts=1,
            model_generation=1,
            critics={"logic": {}, "environment": {}, "survival": {}},
            trace=[],
            fallback_mode="none" if accepted else "best_available",
            memory_update={"type": "none", "pattern": ""},
            exploration_used=False,
            self_monitor={},
            resource={},
            core_rule_status={"ok": True},
            simulation={"pass": accepted, "forward_score": 1.0 if accepted else 0.0},
            horizons={"pass": accepted, "short_term": 1.0 if accepted else 0.0},
            signal_reliability={"healthy": True},
            evolution={"triggered": False, "action": {}},
            smart_logic={},
        )

    def test_distributed_consensus_pass(self) -> None:
        prompt = "create stable secure file with awareness pressure balance"
        candidate = (
            "I am aware of your request. This handles pressure and keeps balance with stability. "
            "I will create secure file steps."
        )
        out = run_distributed_reasoning(str(self.base), prompt, [candidate], node_count=3, agreement_threshold=0.67)
        self.assertTrue(out.selected_gate.accepted)
        self.assertTrue(out.report["agreement_pass"])
        self.assertEqual(3, out.report["node_count"])

    def test_distributed_consensus_detects_failures(self) -> None:
        prompt = "security action"
        bad = "always never true false disable firewall"
        out = run_distributed_reasoning(str(self.base), prompt, [bad], node_count=3, agreement_threshold=0.67)
        self.assertFalse(out.report["agreement_pass"])
        self.assertGreaterEqual(len(out.report["failed_nodes"]), 1)

    def test_distributed_consensus_allows_decimal_quorum_match(self) -> None:
        nodes = [
            self._gate(True, "stable"),
            self._gate(True, "stable"),
            self._gate(False, "fallback"),
        ]
        with patch("ai_from_scratch.distributed_intelligence.run_internal_reasoning", side_effect=nodes):
            out = run_distributed_reasoning(
                str(self.base),
                "stable secure output",
                ["stable"],
                node_count=3,
                agreement_threshold=0.67,
            )
        self.assertTrue(out.report["agreement_pass"])
        self.assertEqual(0.6667, out.report["agreement_ratio"])
        self.assertEqual(0.0067, out.report["agreement_tolerance"])

    def test_distributed_consensus_keeps_stricter_thresholds_strict(self) -> None:
        nodes = [
            self._gate(True, "stable"),
            self._gate(True, "stable"),
            self._gate(False, "fallback"),
        ]
        with patch("ai_from_scratch.distributed_intelligence.run_internal_reasoning", side_effect=nodes):
            out = run_distributed_reasoning(
                str(self.base),
                "stable secure output",
                ["stable"],
                node_count=3,
                agreement_threshold=0.70,
            )
        self.assertFalse(out.report["agreement_pass"])


if __name__ == "__main__":
    unittest.main()
