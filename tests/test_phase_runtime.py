import json
import os
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

from zero_os.assistant_job_runner import schedule_recurring_builtin
from zero_os.phase_runtime import (
    _runtime_loop_default,
    zero_ai_runtime_agent_ensure,
    zero_ai_runtime_agent_install,
    zero_ai_runtime_agent_start,
    zero_ai_runtime_agent_status,
    zero_ai_runtime_agent_stop,
    zero_ai_runtime_agent_uninstall,
    zero_ai_runtime_loop_run,
    zero_ai_runtime_loop_set,
    zero_ai_runtime_loop_status,
    zero_ai_runtime_loop_tick,
    zero_ai_runtime_run,
    zero_ai_runtime_status,
)
from zero_os.self_continuity import zero_ai_continuity_governance_set, zero_ai_self_continuity_update
from zero_os.zero_ai_identity import zero_ai_identity


class ZeroAIRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_ai_runtime_")
        self.base = Path(self.tempdir)

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_runtime_run_turns_off_background_continuity_when_stable(self) -> None:
        zero_ai_identity(str(self.base))
        zero_ai_self_continuity_update(str(self.base))
        zero_ai_continuity_governance_set(str(self.base), True, 120)
        schedule_recurring_builtin(str(self.base), "continuity_governance", interval_seconds=120, enabled=True)

        runtime = zero_ai_runtime_run(str(self.base))

        self.assertTrue(runtime["ok"])
        managed = runtime["continuity_governance_background"]
        self.assertTrue(managed["ok"])
        self.assertFalse(managed["auto"]["recommended_enabled"])
        self.assertFalse(managed["continuity_governance"]["enabled"])
        self.assertEqual(0, managed["jobs"]["recurring_count"])
        self.assertFalse(managed["tick"]["ticked"])
        self.assertIn("autonomy", runtime)
        self.assertIn("autonomy_background", runtime)
        self.assertIn("control_workflows", runtime)
        self.assertIn("capability_control_map", runtime)
        self.assertIn("evolution", runtime)
        self.assertIn("source_evolution", runtime)
        self.assertTrue(runtime["autonomy"]["ok"])
        self.assertTrue(runtime["autonomy_background"]["ok"])
        self.assertTrue(runtime["control_workflows"]["ok"])
        self.assertTrue(runtime["capability_control_map"]["ok"])
        self.assertTrue(runtime["evolution"]["ok"])
        self.assertTrue(runtime["source_evolution"]["ok"])

        saved = zero_ai_runtime_status(str(self.base))
        self.assertIn("continuity_governance_background", saved)
        self.assertIn("autonomy", saved)
        self.assertIn("control_workflows", saved)
        self.assertIn("capability_control_map", saved)
        self.assertIn("evolution", saved)
        self.assertIn("source_evolution", saved)

    def test_runtime_run_turns_on_background_continuity_when_risky(self) -> None:
        zero_ai_identity(str(self.base))
        snapshot = self.base / ".zero_os" / "runtime" / "zero_ai_identity_snapshot.json"
        payload = json.loads(snapshot.read_text(encoding="utf-8"))
        payload["classification"] = "unsafe_mutation_engine"
        payload["is_rsi"] = True
        snapshot.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        zero_ai_self_continuity_update(str(self.base))

        runtime = zero_ai_runtime_run(str(self.base))

        self.assertTrue(runtime["ok"])
        managed = runtime["continuity_governance_background"]
        self.assertTrue(managed["ok"])
        self.assertTrue(managed["auto"]["recommended_enabled"])
        self.assertTrue(managed["continuity_governance"]["enabled"])
        self.assertGreaterEqual(managed["jobs"]["recurring_count"], 1)
        self.assertTrue(managed["tick"]["ticked"])
        self.assertTrue(managed["tick"]["result"]["ok"])

    def test_runtime_loop_status_defaults(self) -> None:
        status = zero_ai_runtime_loop_status(str(self.base))
        self.assertTrue(status["ok"])
        self.assertFalse(status["enabled"])
        self.assertEqual(_runtime_loop_default()["interval_seconds"], status["interval_seconds"])
        self.assertFalse(status["due_now"])

    def test_runtime_loop_tick_when_off_is_noop(self) -> None:
        tick = zero_ai_runtime_loop_tick(str(self.base))
        self.assertTrue(tick["ok"])
        self.assertFalse(tick["ran"])
        self.assertEqual("runtime loop is off", tick["reason"])

    def test_runtime_loop_run_updates_state_when_enabled(self) -> None:
        zero_ai_identity(str(self.base))
        zero_ai_runtime_loop_set(str(self.base), True, 120)

        tick = zero_ai_runtime_loop_tick(str(self.base), force=True)

        self.assertTrue(tick["ok"])
        self.assertTrue(tick["ran"])
        self.assertTrue(tick["runtime_loop"]["enabled"])
        self.assertNotEqual("", tick["runtime_loop"]["last_run_utc"])
        self.assertNotEqual("", tick["runtime_loop"]["next_run_utc"])

    def test_runtime_loop_backoff_records_failure(self) -> None:
        zero_ai_runtime_loop_set(str(self.base), True, 120)

        with patch("zero_os.phase_runtime.zero_ai_runtime_run", return_value={"ok": False, "reason": "forced failure"}):
            tick = zero_ai_runtime_loop_run(str(self.base))

        self.assertFalse(tick["ok"])
        self.assertTrue(tick["ran"])
        self.assertEqual("forced failure", tick["runtime_loop"]["last_failure"])
        self.assertEqual(1, tick["runtime_loop"]["consecutive_failures"])
        self.assertGreaterEqual(tick["runtime_loop"]["backoff_seconds"], 120)

    def test_runtime_agent_install_and_uninstall_manage_startup_artifact(self) -> None:
        startup_dir = self.base / "startup"
        now = datetime.now(timezone.utc).isoformat()
        with patch.dict(os.environ, {"ZERO_OS_RUNTIME_AGENT_STARTUP_DIR": str(startup_dir)}):
            with patch("zero_os.phase_runtime._launch_runtime_agent", return_value={"ok": True, "pid": 4321, "started_utc": now, "command": ["python", "zero_os_runtime_agent.py"]}), \
                 patch("zero_os.phase_runtime._pid_alive", return_value=True), \
                 patch("zero_os.phase_runtime._terminate_pid", return_value=True):
                installed = zero_ai_runtime_agent_install(str(self.base))
                self.assertTrue(installed["ok"])
                self.assertTrue(installed["agent"]["installed"])
                self.assertTrue(Path(installed["startup_launcher_path"]).exists())

                status = zero_ai_runtime_agent_status(str(self.base))
                self.assertTrue(status["running"])
                self.assertEqual(4321, status["worker_pid"])

                uninstalled = zero_ai_runtime_agent_uninstall(str(self.base))
                self.assertTrue(uninstalled["ok"])
                self.assertFalse(uninstalled["agent"]["installed"])
                self.assertFalse(Path(installed["startup_launcher_path"]).exists())

    def test_runtime_agent_start_and_stop_update_state(self) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with patch("zero_os.phase_runtime._launch_runtime_agent", return_value={"ok": True, "pid": 2468, "started_utc": now, "command": ["python", "zero_os_runtime_agent.py"]}), \
             patch("zero_os.phase_runtime._pid_alive", return_value=True), \
             patch("zero_os.phase_runtime._terminate_pid", return_value=True):
            started = zero_ai_runtime_agent_start(str(self.base))
            self.assertTrue(started["ok"])
            self.assertTrue(started["started"])
            self.assertTrue(started["agent"]["runtime_loop"]["enabled"])

            stopped = zero_ai_runtime_agent_stop(str(self.base))
            self.assertTrue(stopped["ok"])
            self.assertTrue(stopped["stopped"])
            self.assertFalse(stopped["agent"]["running"])

    def test_runtime_agent_status_uses_startup_grace_after_launch(self) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with patch(
            "zero_os.phase_runtime._launch_runtime_agent",
            return_value={"ok": True, "pid": 2468, "started_utc": now, "command": ["python", "zero_os_runtime_agent.py"]},
        ), patch("zero_os.phase_runtime._pid_alive", return_value=True):
            started = zero_ai_runtime_agent_start(str(self.base))

        self.assertTrue(started["ok"])
        self.assertTrue(started["agent"]["running"])
        self.assertTrue(started["agent"]["startup_grace_active"])

    def test_runtime_agent_ensure_installs_when_missing(self) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with patch(
            "zero_os.phase_runtime._launch_runtime_agent",
            return_value={"ok": True, "pid": 1357, "started_utc": now, "command": ["python", "zero_os_runtime_agent.py"]},
        ), patch("zero_os.phase_runtime._pid_alive", return_value=True):
            ensured = zero_ai_runtime_agent_ensure(str(self.base))

        self.assertTrue(ensured["ok"])
        self.assertTrue(ensured["changed"])
        self.assertEqual("install", ensured["action"])
        self.assertTrue(ensured["agent"]["running"])


if __name__ == "__main__":
    unittest.main()
