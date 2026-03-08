import shutil
import tempfile
import unittest
from pathlib import Path

from ai_from_scratch.outcome_observation_layer import observe_outcome


class _GateStub:
    def __init__(self, attempts_used: int, attempt_limit: int, avg_conf: float) -> None:
        self.resource = {"attempts_used": attempts_used, "attempt_limit": attempt_limit}
        self.self_monitor = {"avg_confidence_recent": avg_conf}


class OutcomeObservationLayerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_outcome_")
        self.base = Path(self.tempdir)

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_observes_success_metrics(self) -> None:
        gate = _GateStub(2, 9, 0.8)
        execution = {"executed": True, "dispatch": {"allowed": True}}
        out = observe_outcome(
            str(self.base),
            "status",
            execution,
            gate,
            {"reasoning_parameters": {"priority_mode": "normal"}},
        )
        self.assertTrue(out["ok"])
        self.assertTrue(out["observed"]["actual_success"])
        self.assertGreater(out["observed"]["efficiency_score"], 0.5)

    def test_observes_failure_metrics(self) -> None:
        gate = _GateStub(9, 9, 0.2)
        execution = {"executed": False, "dispatch": {"allowed": False}}
        out = observe_outcome(
            str(self.base),
            "status",
            execution,
            gate,
            {"reasoning_parameters": {"priority_mode": "normal"}},
        )
        self.assertFalse(out["observed"]["actual_success"])
        self.assertLess(out["metrics"]["stability_impact"], 1.0)


if __name__ == "__main__":
    unittest.main()

