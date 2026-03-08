import shutil
import tempfile
import unittest
from pathlib import Path

from ai_from_scratch.signal_fusion_layer import fuse_signals


class SignalFusionLayerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_fusion_")
        self.base = Path(self.tempdir)
        self.context = {"reasoning_parameters": {"priority_mode": "normal"}}

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_stable_fusion_when_all_signals_aligned(self) -> None:
        critics = {
            "logic": {"pass": True, "confidence": 0.9},
            "environment": {"pass": True, "confidence": 0.8},
            "survival": {"pass": True, "confidence": 0.9},
        }
        out = fuse_signals(str(self.base), critics, self.context, {"status": {"logic": 1, "environment": 1, "survival": 1}})
        self.assertTrue(out["stable"])
        self.assertFalse(out["conflict_detected"])

    def test_conflict_detected_when_signal_disagrees(self) -> None:
        critics = {
            "logic": {"pass": True, "confidence": 0.9},
            "environment": {"pass": False, "confidence": 0.2},
            "survival": {"pass": True, "confidence": 0.9},
        }
        out = fuse_signals(str(self.base), critics, self.context, {"status": {"logic": 1, "environment": 1, "survival": 1}})
        self.assertTrue(out["conflict_detected"])
        self.assertFalse(out["stable"])


if __name__ == "__main__":
    unittest.main()

