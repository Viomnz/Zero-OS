import shutil
import tempfile
import unittest
from pathlib import Path

from ai_from_scratch.calibration_layer import run_calibration
from ai_from_scratch.signal_reliability import update_signal_reliability


class CalibrationLayerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_calibration_")
        self.base = Path(self.tempdir)

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_calibration_writes_state_and_returns_actions(self) -> None:
        critics = {
            "logic": {"confidence": 0.3},
            "environment": {"confidence": 0.2},
            "survival": {"confidence": 0.3},
        }
        update_signal_reliability(str(self.base), critics)
        out = run_calibration(str(self.base))
        self.assertTrue(out["ok"])
        self.assertIn("reliability_before", out)
        self.assertIn("reliability_after", out)
        self.assertIn("actions", out)
        state = self.base / ".zero_os" / "runtime" / "calibration_state.json"
        self.assertTrue(state.exists())


if __name__ == "__main__":
    unittest.main()

