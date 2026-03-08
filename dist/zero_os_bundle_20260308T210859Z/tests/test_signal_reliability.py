import shutil
import tempfile
import unittest
from pathlib import Path

from ai_from_scratch.signal_reliability import (
    apply_reliability_calibration,
    evaluate_signal_reliability,
    update_signal_reliability,
)


class SignalReliabilityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_signal_rel_")
        self.base = Path(self.tempdir)

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_default_reliability_is_healthy(self) -> None:
        out = evaluate_signal_reliability(str(self.base))
        self.assertTrue(out["healthy"])
        self.assertTrue(out["actions"]["allow_execution"])

    def test_update_reliability_changes_current(self) -> None:
        critics = {
            "logic": {"confidence": 0.2},
            "environment": {"confidence": 0.1},
            "survival": {"confidence": 0.3},
        }
        update_signal_reliability(str(self.base), critics)
        out = evaluate_signal_reliability(str(self.base))
        self.assertLess(out["status"]["environment"], 1.0)

    def test_apply_calibration_moves_toward_targets(self) -> None:
        critics = {
            "logic": {"confidence": 0.2},
            "environment": {"confidence": 0.2},
            "survival": {"confidence": 0.2},
        }
        update_signal_reliability(str(self.base), critics)
        before = evaluate_signal_reliability(str(self.base))
        apply_reliability_calibration(str(self.base), {"logic": 1.0, "environment": 1.0, "survival": 1.0}, strength=0.5)
        after = evaluate_signal_reliability(str(self.base))
        self.assertGreater(after["status"]["logic"], before["status"]["logic"])


if __name__ == "__main__":
    unittest.main()
