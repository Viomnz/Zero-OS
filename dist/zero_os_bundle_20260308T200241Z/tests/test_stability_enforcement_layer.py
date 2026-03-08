import shutil
import tempfile
import unittest
from pathlib import Path

from ai_from_scratch.stability_enforcement_layer import enforce_stability


class _GateStub:
    def __init__(self, attempts_used: int, attempt_limit: int) -> None:
        self.resource = {"attempts_used": attempts_used, "attempt_limit": attempt_limit}


class StabilityEnforcementLayerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_stability_")
        self.base = Path(self.tempdir)

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_stable_candidate_passes(self) -> None:
        gate = _GateStub(2, 9)
        out = enforce_stability(
            str(self.base),
            "optimize system",
            "apply safe optimization plan",
            gate,
            {"reasoning_parameters": {"priority_mode": "normal"}},
        )
        self.assertTrue(out["stable"])

    def test_high_resource_pressure_fails(self) -> None:
        gate = _GateStub(9, 9)
        out = enforce_stability(
            str(self.base),
            "optimize system",
            "apply safe optimization plan",
            gate,
            {"reasoning_parameters": {"priority_mode": "normal"}},
        )
        self.assertFalse(out["stable"])


if __name__ == "__main__":
    unittest.main()

