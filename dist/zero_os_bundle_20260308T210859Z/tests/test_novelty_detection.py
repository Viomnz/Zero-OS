import shutil
import tempfile
import unittest
from pathlib import Path

from ai_from_scratch.novelty_detection import detect_novelty


class NoveltyDetectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_novelty_")
        self.base = Path(self.tempdir)

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_detects_novel_input(self) -> None:
        out = detect_novelty(str(self.base), "quantum lattice scheduler for alien bytecode", "human")
        self.assertTrue(out["ok"])
        self.assertTrue(out["is_novel"])
        self.assertEqual("exploration", out["actions"]["set_mode"])
        self.assertEqual("adaptive", out["actions"]["set_profile"])

    def test_detects_known_pattern(self) -> None:
        detect_novelty(str(self.base), "optimize memory and storage", "human")
        out = detect_novelty(str(self.base), "optimize memory and storage", "human")
        self.assertTrue(out["ok"])
        self.assertFalse(out["is_novel"])
        self.assertEqual("stability", out["actions"]["set_mode"])


if __name__ == "__main__":
    unittest.main()

