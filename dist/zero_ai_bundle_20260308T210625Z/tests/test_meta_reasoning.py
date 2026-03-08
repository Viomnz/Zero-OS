import shutil
import tempfile
import unittest
from pathlib import Path

from ai_from_scratch.meta_reasoning import run_meta_reasoning


class MetaReasoningTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_meta_")
        self.base = Path(self.tempdir)

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_selects_fast_path_for_aligned_candidates(self) -> None:
        prompt = "optimize storage monitor status"
        candidates = [
            "optimize storage monitor status with stable execution",
            "status monitor optimize storage now",
        ]
        out = run_meta_reasoning(str(self.base), prompt, candidates)
        self.assertTrue(out["ok"])
        self.assertIn(out["strategy"], {"fast_path", "balanced_path"})
        self.assertIn("reasoning_analysis", out)

    def test_detects_inefficient_path(self) -> None:
        prompt = "simple status"
        long_bad = "x " * 2500
        out = run_meta_reasoning(str(self.base), prompt, [long_bad])
        self.assertTrue(out["reasoning_analysis"]["inefficient_path"])
        self.assertEqual("compressed_path", out["strategy"])


if __name__ == "__main__":
    unittest.main()

