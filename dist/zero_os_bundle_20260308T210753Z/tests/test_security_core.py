import shutil
import tempfile
import unittest
from pathlib import Path

from ai_from_scratch.security_core import (
    assess_security,
    load_policy,
    record_event,
    save_policy,
    scan_reputation,
    trust_file,
)


class SecurityCoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_os_security_core_")
        self.base = Path(self.tempdir)
        rt = self.base / ".zero_os" / "runtime"
        rt.mkdir(parents=True, exist_ok=True)
        (rt / "zero_ai_tasks.txt").write_text("", encoding="utf-8")
        (rt / "zero_ai_output.txt").write_text("", encoding="utf-8")

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_policy_roundtrip(self) -> None:
        pol = load_policy(self.base)
        self.assertIn("max_pending_tasks", pol)
        out = save_policy(self.base, {"max_pending_tasks": 12})
        self.assertEqual(out["max_pending_tasks"], 12)

    def test_event_chain_has_hash(self) -> None:
        ev = record_event(self.base, "INFO", "boot", {"ok": True})
        self.assertIn("hash", ev)
        self.assertIn("prev_hash", ev)

    def test_assess_security_healthy_when_empty(self) -> None:
        rep = assess_security(self.base, 0)
        self.assertTrue(rep["healthy"])

    def test_reputation_scan_flags_unknown_then_passes_when_trusted(self) -> None:
        f = self.base / "tool.ps1"
        f.write_text("Write-Output 'ok'\n", encoding="utf-8")

        first = scan_reputation(self.base)
        self.assertFalse(first["healthy"])
        self.assertEqual(len(first["unknown"]), 1)

        trust_file(self.base, "tool.ps1", score=90, level="trusted", note="approved")
        second = scan_reputation(self.base)
        self.assertTrue(second["healthy"])
        self.assertEqual(len(second["unknown"]), 0)


if __name__ == "__main__":
    unittest.main()
