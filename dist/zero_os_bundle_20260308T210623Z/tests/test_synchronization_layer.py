import json
import os
import shutil
import tempfile
import time
import unittest
from pathlib import Path

from ai_from_scratch.synchronization_layer import run_synchronization


class SynchronizationLayerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_sync_")
        self.base = Path(self.tempdir)
        (self.base / ".zero_os" / "runtime").mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def _write_state(self, name: str, payload: dict) -> Path:
        p = self.base / ".zero_os" / "runtime" / name
        p.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        return p

    def test_pass_when_no_state_files(self) -> None:
        out = run_synchronization(str(self.base))
        self.assertTrue(out["ok"])
        self.assertEqual(out["reason"], "no state files yet")

    def test_pass_when_state_files_aligned(self) -> None:
        self._write_state("boot_initialization.json", {"ok": True})
        self._write_state("boundary_scope.json", {"ok": True})
        out = run_synchronization(str(self.base), max_skew_seconds=300.0)
        self.assertTrue(out["ok"])
        self.assertEqual(out["stale_modules"], [])

    def test_fail_when_state_files_skewed(self) -> None:
        old = self._write_state("boot_initialization.json", {"ok": True})
        now = time.time()
        os.utime(old, (now - 1000, now - 1000))
        self._write_state("boundary_scope.json", {"ok": True})
        out = run_synchronization(str(self.base), max_skew_seconds=300.0)
        self.assertFalse(out["ok"])
        self.assertIn("boot_initialization.json", out["stale_modules"])


if __name__ == "__main__":
    unittest.main()

