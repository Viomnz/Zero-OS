import json
import shutil
import tempfile
import unittest
from pathlib import Path

from ai_from_scratch.boot_initialization import run_boot_initialization


class BootInitializationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_boot_")
        self.base = Path(self.tempdir)
        (self.base / "ai_from_scratch").mkdir(parents=True, exist_ok=True)
        (self.base / ".zero_os" / "runtime").mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_boot_fails_without_checkpoint(self) -> None:
        out = run_boot_initialization(str(self.base))
        self.assertFalse(out["ok"])
        self.assertTrue(out["safe_mode"])

    def test_boot_passes_with_valid_checkpoint_and_memory(self) -> None:
        (self.base / "ai_from_scratch" / "checkpoint.json").write_text(
            json.dumps({"table": [[0, 1], [1, 0]], "vocab_size": 2}),
            encoding="utf-8",
        )
        (self.base / ".zero_os" / "runtime" / "internal_zero_reasoner_memory.json").write_text(
            json.dumps({"success_patterns": [], "failure_patterns": []}),
            encoding="utf-8",
        )
        out = run_boot_initialization(str(self.base))
        self.assertTrue(out["ok"])
        self.assertFalse(out["safe_mode"])


if __name__ == "__main__":
    unittest.main()

