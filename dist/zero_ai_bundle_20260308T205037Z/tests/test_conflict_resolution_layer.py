import shutil
import tempfile
import unittest
from pathlib import Path

from ai_from_scratch.conflict_resolution_layer import resolve_conflicts


class _GateStub:
    def __init__(self, output: str, critics: dict) -> None:
        self.output = output
        self.critics = critics


class ConflictResolutionLayerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_conflict_")
        self.base = Path(self.tempdir)

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_detects_node_disagreement(self) -> None:
        gate = _GateStub(
            "stable secure action",
            {
                "logic": {"pass": True, "confidence": 0.9},
                "environment": {"pass": True, "confidence": 0.8},
                "survival": {"pass": True, "confidence": 0.9},
            },
        )
        arbitration = {"ok": True, "winner": "stable secure action", "winner_score": 0.7}
        out = resolve_conflicts(
            str(self.base),
            "secure system",
            {"agreement_pass": False},
            gate,
            arbitration,
        )
        self.assertTrue(out["ok"])
        self.assertTrue(out["conflicts"]["node_disagreement"])

    def test_reasoning_conflict_chooses_higher_score(self) -> None:
        gate = _GateStub(
            "action_a",
            {
                "logic": {"pass": True, "confidence": 0.5},
                "environment": {"pass": True, "confidence": 0.5},
                "survival": {"pass": True, "confidence": 0.5},
            },
        )
        arbitration = {"ok": True, "winner": "action_b", "winner_score": 0.9}
        out = resolve_conflicts(
            str(self.base),
            "optimize memory",
            {"agreement_pass": True},
            gate,
            arbitration,
        )
        self.assertTrue(out["conflicts"]["reasoning_conflict"])
        self.assertEqual("action_b", out["chosen_output"])


if __name__ == "__main__":
    unittest.main()

