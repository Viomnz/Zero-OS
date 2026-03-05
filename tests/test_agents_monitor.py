import json
import shutil
import tempfile
import unittest
from pathlib import Path

from ai_from_scratch.agents_monitor import run_agents_monitor


class AgentsMonitorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_agents_monitor_")
        self.base = Path(self.tempdir)
        self.runtime = self.base / ".zero_os" / "runtime"
        self.runtime.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def _write(self, name: str, payload: dict) -> None:
        (self.runtime / name).write_text(json.dumps(payload), encoding="utf-8")

    def test_smooth_when_all_checks_pass(self) -> None:
        self._write("zero_ai_heartbeat.json", {"status": "running"})
        self._write("agent_health.json", {"healthy": True})
        self._write("boot_initialization.json", {"ok": True})
        self._write("safe_state_report.json", {"enter_safe_state": False})
        self._write("agi_module_registry_status.json", {"ok": True})
        self._write("agi_advanced_layers_status.json", {"ok": True})
        out = run_agents_monitor(str(self.base))
        self.assertTrue(out["smooth"])
        self.assertEqual(out["issues"], [])

    def test_reports_issues_when_core_signals_fail(self) -> None:
        self._write("zero_ai_heartbeat.json", {"status": "safe_mode"})
        self._write("agent_health.json", {"healthy": False})
        self._write("boot_initialization.json", {"ok": False})
        self._write("safe_state_report.json", {"enter_safe_state": True})
        self._write("agi_module_registry_status.json", {"ok": False})
        self._write("agi_advanced_layers_status.json", {"ok": False})
        out = run_agents_monitor(str(self.base))
        self.assertFalse(out["smooth"])
        self.assertGreaterEqual(len(out["issues"]), 4)


if __name__ == "__main__":
    unittest.main()

