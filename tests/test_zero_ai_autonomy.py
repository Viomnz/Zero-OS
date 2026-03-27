import json
import re
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

from zero_os.approval_workflow import request_approval
from zero_os.phase_runtime import zero_ai_runtime_run
from zero_os.self_continuity import zero_ai_self_continuity_update
from zero_os.zero_ai_autonomy import (
    zero_ai_autonomy_add_goal,
    zero_ai_autonomy_drain,
    zero_ai_autonomy_loop_set,
    zero_ai_autonomy_loop_tick,
    zero_ai_autonomy_run,
    zero_ai_autonomy_status,
    zero_ai_autonomy_sync,
)
from zero_os.zero_ai_evolution import zero_ai_evolution_auto_run
from zero_os.zero_ai_identity import zero_ai_identity


class ZeroAiAutonomyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_ai_autonomy_")
        self.base = Path(self.tempdir)

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def _prime_identity(self) -> None:
        zero_ai_identity(str(self.base))
        zero_ai_self_continuity_update(str(self.base))

    def _prime_stable_runtime(self) -> None:
        self._prime_identity()
        runtime_dir = self.base / ".zero_os" / "runtime"
        runtime_dir.mkdir(parents=True, exist_ok=True)
        now = datetime.now(timezone.utc).isoformat()
        (runtime_dir / "runtime_agent_state.json").write_text(
            json.dumps(
                {
                    "installed": True,
                    "auto_start_on_login": True,
                    "running": True,
                    "worker_pid": 4321,
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
                    "interval_seconds": 180,
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

    def _stage_source_targets(self) -> None:
        for relative in (
            Path("src/zero_os/phase_runtime.py"),
            Path("src/zero_os/zero_ai_autonomy.py"),
            Path("src/zero_os/zero_ai_control_workflows.py"),
            Path("src/zero_os/self_continuity.py"),
            Path("src/zero_os/triad_balance.py"),
            Path("src/zero_os/antivirus.py"),
        ):
            source = ROOT / relative
            target = self.base / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            content = source.read_text(encoding="utf-8", errors="replace")
            if relative.name == "phase_runtime.py":
                content = re.sub(
                    r'(def _runtime_loop_default\(\) -> dict:\s+return \{\s+"enabled": False,\s+"interval_seconds": )(\d+)',
                    r"\g<1>180",
                    content,
                    count=1,
                    flags=re.S,
                )
            if relative.name == "zero_ai_autonomy.py":
                content = re.sub(
                    r'(def _loop_state_default\(\) -> dict:\s+return \{\s+"enabled": False,\s+"interval_seconds": )(\d+)',
                    r"\g<1>300",
                    content,
                    count=1,
                    flags=re.S,
                )
            if relative.name == "zero_ai_control_workflows.py":
                content = re.sub(
                    r'("self_repair": \{\s+"enabled": True,\s+"mode": "canary_backed",\s+"minimum_readiness_floor": )(\d+)',
                    r"\g<1>60",
                    content,
                    count=1,
                    flags=re.S,
                )
            if relative.name == "self_continuity.py":
                content = re.sub(
                    r'(def _governance_default\(\) -> dict\[str, Any\]:\s+return \{\s+"enabled": False,\s+"interval_seconds": )(\d+)',
                    r"\g<1>180",
                    content,
                    count=1,
                    flags=re.S,
                )
            if relative.name == "triad_balance.py":
                content = re.sub(
                    r'(def triad_ops_status\(cwd: str\) -> dict:\s+default = \{\s+"enabled": False,\s+"interval_seconds": )(\d+)',
                    r"\g<1>180",
                    content,
                    count=1,
                    flags=re.S,
                )
            if relative.name == "antivirus.py":
                content = re.sub(
                    r'(def monitor_status\(cwd: str\) -> dict:\s+default = \{"enabled": False, "last_tick_utc": "", "last_scan_path": "\.", "interval_seconds": )(\d+)',
                    r"\g<1>120",
                    content,
                    count=1,
                    flags=re.S,
                )
            target.write_text(content, encoding="utf-8")

    def test_autonomy_sync_prioritizes_runtime_when_runtime_missing(self) -> None:
        self._prime_identity()

        synced = zero_ai_autonomy_sync(str(self.base))

        self.assertTrue(synced["ok"])
        self.assertIn("control_workflows", synced["status"])
        self.assertIn("capability_control_map", synced["status"])
        self.assertIn("world_model", synced["status"])
        self.assertIn("decision_governor", synced["status"])
        self.assertFalse(synced["status"]["capability_control_map"]["fully_autonomous_control"])
        current = synced["status"]["current_goal"]
        self.assertIsNotNone(current)
        self.assertEqual("stabilize_runtime", current["key"])
        self.assertEqual("run_runtime", current["action_kind"])
        self.assertEqual("run_runtime", synced["signals"]["governor_call"])

    def test_autonomy_run_executes_runtime_goal(self) -> None:
        self._prime_identity()

        run = zero_ai_autonomy_run(str(self.base))

        self.assertTrue(run["ok"])
        self.assertTrue(run["ran"])
        self.assertEqual("run_runtime", run["execution"]["action_kind"])
        self.assertTrue(run["execution"]["result"]["ok"])
        self.assertTrue(run["autonomy"]["runtime_ready"])

    def test_autonomy_status_surfaces_blocked_approval_goal(self) -> None:
        self._prime_stable_runtime()
        request_approval(str(self.base), "self_repair", "policy_requires_approval", {"target": "runtime"})

        with patch("zero_os.phase_runtime._pid_alive", return_value=True):
            status = zero_ai_autonomy_status(str(self.base))

        self.assertGreaterEqual(status["blocked_count"], 1)
        self.assertIn("control_workflows", status)
        self.assertIn("capability_control_map", status)
        self.assertIn("world_model", status)
        self.assertIn("decision_governor", status)
        blocked = next(goal for goal in status["goals"] if goal["key"] == "pending_approvals")
        self.assertEqual("blocked", blocked["state"])
        self.assertEqual("wait_for_user", status["decision_governor"]["call"])

    def test_expired_approvals_stop_blocking_autonomy(self) -> None:
        self._prime_stable_runtime()
        request_approval(str(self.base), "self_repair", "policy_requires_approval", {"target": "runtime"})
        approvals_path = self.base / ".zero_os" / "assistant" / "approvals.json"
        payload = json.loads(approvals_path.read_text(encoding="utf-8"))
        payload["items"][0]["expires_utc"] = "2000-01-01T00:00:00+00:00"
        approvals_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

        with patch("zero_os.phase_runtime._pid_alive", return_value=True):
            status = zero_ai_autonomy_status(str(self.base))

        self.assertEqual(0, status["blocked_count"])
        self.assertEqual(0, status["approvals_pending"])
        self.assertGreaterEqual(status["approvals_expired"], 1)

    def test_autonomy_drain_stops_cleanly_on_blocked_goal(self) -> None:
        self._prime_stable_runtime()
        request_approval(str(self.base), "self_repair", "policy_requires_approval", {"target": "runtime"})

        with patch("zero_os.phase_runtime._pid_alive", return_value=True):
            drained = zero_ai_autonomy_drain(str(self.base), max_runs=3)

        self.assertTrue(drained["ok"])
        self.assertFalse(drained["ran"])
        self.assertIn("approval item", drained["reason"])

    def test_manual_goal_runs_and_resolves_in_stable_state(self) -> None:
        self._prime_stable_runtime()

        with patch("zero_os.phase_runtime._pid_alive", return_value=True):
            added = zero_ai_autonomy_add_goal(str(self.base), "check system status", priority=99)
            self.assertTrue(added["ok"])

            run = zero_ai_autonomy_run(str(self.base))
            self.assertTrue(run["ok"])
            self.assertEqual("request_task", run["execution"]["action_kind"])

            status = zero_ai_autonomy_status(str(self.base))

        manual = next(goal for goal in status["goals"] if goal["key"].startswith("manual_check_system_status"))
        self.assertEqual("resolved", manual["state"])

    def test_autonomy_loop_tick_runs_due_goal(self) -> None:
        self._prime_identity()
        zero_ai_autonomy_loop_set(str(self.base), True, 120)

        tick = zero_ai_autonomy_loop_tick(str(self.base), force=True)

        self.assertTrue(tick["ran"])
        self.assertTrue(tick["ok"])
        self.assertEqual("run_runtime", tick["result"]["execution"]["action_kind"])

    def test_autonomy_sync_surfaces_bounded_self_evolution_goal(self) -> None:
        self._prime_stable_runtime()
        zero_ai_autonomy_loop_set(str(self.base), True, 300)

        with patch("zero_os.phase_runtime._pid_alive", return_value=True):
            status = zero_ai_autonomy_sync(str(self.base))["status"]

        current = status["current_goal"]
        self.assertIsNotNone(current)
        self.assertEqual("self_evolve", current["key"])
        self.assertEqual("evolution_auto_run", current["action_kind"])

    def test_autonomy_run_executes_bounded_self_evolution_goal(self) -> None:
        self._prime_stable_runtime()
        zero_ai_autonomy_loop_set(str(self.base), True, 300)

        with patch("zero_os.phase_runtime._pid_alive", return_value=True):
            run = zero_ai_autonomy_run(str(self.base))

        self.assertTrue(run["ok"])
        self.assertTrue(run["ran"])
        self.assertEqual("evolution_auto_run", run["execution"]["action_kind"])
        self.assertEqual(1, run["execution"]["result"]["status"]["current_generation"])

    def test_autonomy_sync_surfaces_guarded_source_evolution_goal(self) -> None:
        self._prime_stable_runtime()
        self._stage_source_targets()
        with patch("zero_os.phase_runtime._pid_alive", return_value=True):
            zero_ai_autonomy_loop_set(str(self.base), True, 300)
            evolved = zero_ai_evolution_auto_run(str(self.base))
            self.assertTrue(evolved["ok"])
            status = zero_ai_autonomy_sync(str(self.base))["status"]

        current = status["current_goal"]
        self.assertIsNotNone(current)
        self.assertEqual("source_evolve", current["key"])
        self.assertEqual("source_evolution_auto_run", current["action_kind"])


if __name__ == "__main__":
    unittest.main()
