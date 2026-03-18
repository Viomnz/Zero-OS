import json
import shutil
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from zero_os.phase_runtime import zero_ai_runtime_run
from zero_os.self_continuity import zero_ai_self_continuity_update
from zero_os.zero_ai_capability_map import zero_ai_capability_map_status
from zero_os.zero_ai_identity import zero_ai_identity


class ZeroAiCapabilityMapTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_ai_capability_map_")
        self.base = Path(self.tempdir)

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def _prime_runtime(self) -> None:
        zero_ai_identity(str(self.base))
        zero_ai_self_continuity_update(str(self.base))
        runtime_dir = self.base / ".zero_os" / "runtime"
        runtime_dir.mkdir(parents=True, exist_ok=True)
        now = datetime.now(timezone.utc).isoformat()
        (runtime_dir / "runtime_agent_state.json").write_text(
            json.dumps(
                {
                    "installed": True,
                    "auto_start_on_login": True,
                    "running": True,
                    "worker_pid": 7777,
                    "last_heartbeat_utc": now,
                    "poll_interval_seconds": 30,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        (runtime_dir / "runtime_loop_state.json").write_text(
            json.dumps(
                {
                    "enabled": True,
                    "interval_seconds": 240,
                    "last_run_utc": now,
                    "next_run_utc": now,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        with patch("zero_os.phase_runtime._pid_alive", return_value=True):
            runtime = zero_ai_runtime_run(str(self.base))
        self.assertTrue(runtime["ok"])

    def test_capability_map_exposes_control_levels(self) -> None:
        self._prime_runtime()

        with patch("zero_os.phase_runtime._pid_alive", return_value=True):
            status = zero_ai_capability_map_status(str(self.base))

        self.assertTrue(status["ok"])
        self.assertFalse(status["fully_autonomous_control"])
        self.assertGreaterEqual(status["summary"]["autonomous_count"], 10)
        self.assertEqual(0, status["summary"]["approval_gated_count"])
        self.assertGreaterEqual(status["summary"]["forbidden_count"], 3)
        self.assertIn("control_workflows", status)

        capabilities = {item["key"]: item for item in status["capabilities"]}
        self.assertEqual("autonomous", capabilities["runtime_orchestrator"]["control_level"])
        self.assertTrue(capabilities["runtime_orchestrator"]["active"])
        self.assertEqual("autonomous", capabilities["smart_workspace_map"]["control_level"])
        self.assertTrue(capabilities["smart_workspace_map"]["active"])
        self.assertEqual("autonomous", capabilities["integrity_flow_monitor"]["control_level"])
        self.assertTrue(capabilities["integrity_flow_monitor"]["active"])
        self.assertEqual("autonomous", capabilities["contradiction_gate"]["control_level"])
        self.assertTrue(capabilities["contradiction_gate"]["active"])
        self.assertEqual("autonomous", capabilities["pressure_harness"]["control_level"])
        self.assertEqual("autonomous", capabilities["browser_control"]["control_level"])
        self.assertEqual("autonomous", capabilities["store_installation"]["control_level"])
        self.assertEqual("autonomous", capabilities["recovery_restore"]["control_level"])
        self.assertEqual("autonomous", capabilities["high_risk_self_repair"]["control_level"])
        self.assertEqual("forbidden", capabilities["identity_core_rewrite"]["control_level"])

    def test_capability_map_writes_status_file(self) -> None:
        self._prime_runtime()

        with patch("zero_os.phase_runtime._pid_alive", return_value=True):
            status = zero_ai_capability_map_status(str(self.base))

        path = Path(status["map_path"])
        self.assertTrue(path.exists())
        persisted = json.loads(path.read_text(encoding="utf-8"))
        self.assertIn("highest_value_steps", persisted)
        self.assertEqual(status["summary"]["approval_gated_count"], persisted["summary"]["approval_gated_count"])


if __name__ == "__main__":
    unittest.main()
