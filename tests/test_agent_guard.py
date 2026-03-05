import shutil
import tempfile
import unittest
from pathlib import Path

from ai_from_scratch.agent_guard import (
    build_baseline,
    check_health,
    restore_compromised,
)


class AgentGuardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_os_agent_guard_")
        self.base = Path(self.tempdir)
        for rel in [
            "ai_from_scratch/daemon.py",
            "ai_from_scratch/daemon_ctl.py",
            "src/zero_os/cure_firewall.py",
            "src/zero_os/capabilities/system.py",
        ]:
            p = self.base / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(f"seed:{rel}\n", encoding="utf-8")

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_restore_compromised_uses_trusted_snapshot(self) -> None:
        build_baseline(self.base)
        damaged = self.base / "ai_from_scratch/daemon.py"
        damaged.write_text("tampered\n", encoding="utf-8")

        health = check_health(self.base)
        self.assertFalse(health["healthy"])
        restore = restore_compromised(self.base, health)
        self.assertIn("ai_from_scratch/daemon.py", restore["restored_files"])

        fixed = check_health(self.base)
        self.assertTrue(fixed["healthy"])


if __name__ == "__main__":
    unittest.main()
