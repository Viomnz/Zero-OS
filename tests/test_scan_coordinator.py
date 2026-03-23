import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from zero_os.antivirus import scan_target
from zero_os.scan_coordinator import build_workspace_scan_snapshot, workspace_scan_status


class ScanCoordinatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_scan_coordinator_")
        self.base = Path(self.tempdir)
        (self.base / "src" / "zero_os").mkdir(parents=True, exist_ok=True)
        (self.base / "src" / "main.py").write_text("powershell -enc AAAA\nquantum-virus-signature\n", encoding="utf-8")
        (self.base / "src" / "zero_os" / "__init__.py").write_text("__all__ = []\n", encoding="utf-8")
        (self.base / "README.md").write_text("# Zero\n", encoding="utf-8")

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_workspace_scan_snapshot_reuses_hash_cache_for_unchanged_targets(self) -> None:
        first = build_workspace_scan_snapshot(str(self.base), force=True)
        second = build_workspace_scan_snapshot(str(self.base), force=True)
        status = workspace_scan_status(str(self.base))

        self.assertGreaterEqual(first["hash_cache_entry_count"], 1)
        self.assertGreaterEqual(second["hash_cache_hit_count"], 1)
        self.assertIn("src/main.py", second["preferred_firewall_targets"])
        self.assertEqual(second["file_count"], status["file_count"])

    def test_antivirus_scan_can_reuse_shared_snapshot_hashes(self) -> None:
        snapshot = build_workspace_scan_snapshot(str(self.base), force=True)
        report = scan_target(str(self.base), "src/main.py", scan_snapshot=snapshot)

        self.assertTrue(report["ok"])
        self.assertTrue(report["scan_snapshot_reused"])
        self.assertGreaterEqual(report["hash_cache_hit_count"], 1)
        self.assertGreaterEqual(report["finding_count"], 1)

    def test_workspace_scan_snapshot_skips_temp_roots_for_firewall_targets(self) -> None:
        temp_root = self.base / ".tmp_ci_repro" / "Lib" / "site-packages"
        temp_root.mkdir(parents=True, exist_ok=True)
        (temp_root / "noise.py").write_text("print('noise')\n", encoding="utf-8")

        snapshot = build_workspace_scan_snapshot(str(self.base), force=True)

        joined = "\n".join(snapshot["preferred_firewall_targets"])
        self.assertNotIn(".tmp_ci_repro", joined)
