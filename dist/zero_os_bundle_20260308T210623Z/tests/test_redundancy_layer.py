import json
import shutil
import tempfile
import unittest
from pathlib import Path

from ai_from_scratch.redundancy_layer import ensure_redundancy


class RedundancyLayerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_redundancy_")
        self.base = Path(self.tempdir)
        self.runtime = self.base / ".zero_os" / "runtime"
        self.runtime.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_redundancy_ready_with_primary_files(self) -> None:
        (self.runtime / "internal_zero_reasoner_state.json").write_text("{}", encoding="utf-8")
        (self.runtime / "signal_reliability.json").write_text("{}", encoding="utf-8")
        out = ensure_redundancy(str(self.base), min_backups=2)
        self.assertTrue(out["ok"])
        self.assertTrue(out["primary_ok"])
        self.assertTrue(out["failover_ready"])
        self.assertEqual(2, out["backup_count"])

    def test_redundancy_degraded_without_primary(self) -> None:
        out = ensure_redundancy(str(self.base), min_backups=2)
        self.assertFalse(out["ok"])
        self.assertFalse(out["primary_ok"])
        self.assertFalse(out["failover_ready"])


if __name__ == "__main__":
    unittest.main()

