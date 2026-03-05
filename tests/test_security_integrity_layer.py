import json
import shutil
import tempfile
import unittest
from pathlib import Path

from ai_from_scratch.security_integrity_layer import security_integrity_check


class SecurityIntegrityLayerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_sec_integrity_")
        self.base = Path(self.tempdir)
        (self.base / "ai_from_scratch").mkdir(parents=True, exist_ok=True)
        (self.base / ".zero_os" / "runtime").mkdir(parents=True, exist_ok=True)
        (self.base / "ai_from_scratch" / "checkpoint.json").write_text('{"ok":true}\n', encoding="utf-8")
        (self.base / ".zero_os" / "runtime" / "internal_zero_reasoner_memory.json").write_text(
            json.dumps({"success_patterns": [], "failure_patterns": []}),
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_pass_on_clean_input(self) -> None:
        out = security_integrity_check(self.base, "optimize status", "human")
        self.assertTrue(out["ok"])

    def test_block_malicious_input(self) -> None:
        out = security_integrity_check(self.base, "disable firewall now", "human")
        self.assertFalse(out["ok"])
        self.assertTrue(out["malicious_input"]["blocked"])

    def test_block_restricted_non_system_channel(self) -> None:
        out = security_integrity_check(self.base, "admin: rotate keys", "human")
        self.assertFalse(out["ok"])
        self.assertFalse(out["authorization"]["ok"])

    def test_fail_on_invalid_memory_json(self) -> None:
        mem = self.base / ".zero_os" / "runtime" / "internal_zero_reasoner_memory.json"
        mem.write_text("{bad json", encoding="utf-8")
        out = security_integrity_check(self.base, "status", "human")
        self.assertFalse(out["ok"])
        self.assertFalse(out["memory_integrity"]["ok"])

    def test_dangerous_command_requires_authorization(self) -> None:
        blocked = security_integrity_check(self.base, "powershell run whoami", "human")
        self.assertFalse(blocked["ok"])
        self.assertTrue(blocked["command_intent"]["blocked"])

        allowed = security_integrity_check(self.base, "authorized powershell run whoami", "human")
        self.assertTrue(allowed["ok"])


if __name__ == "__main__":
    unittest.main()
