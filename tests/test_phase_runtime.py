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
from zero_os.calendar_time import calendar_reminder_add
from zero_os.communications import communications_draft_add, communications_send_request
from zero_os.self_derivation_engine import (
    _branch_shape_profile,
    _current_planner_version,
    _current_strategy_code_version,
    _strategy_canary_plan,
    _strategy_condition_profile,
)
from zero_os.approval_workflow import decide as approval_decide
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
from zero_os.state_cache import clear_state_cache, state_cache_status
from zero_os.zero_ai_identity import zero_ai_identity


class ZeroAIRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_ai_runtime_")
        self.base = Path(self.tempdir)
        clear_state_cache()

    def tearDown(self) -> None:
        clear_state_cache()
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
        self.assertIn("zero_engine", runtime)
        self.assertIn("zero_engine_background", runtime)
        self.assertIn("control_workflows", runtime)
        self.assertIn("capability_control_map", runtime)
        self.assertIn("evolution", runtime)
        self.assertIn("source_evolution", runtime)
        self.assertTrue(runtime["autonomy"]["ok"])
        self.assertTrue(runtime["autonomy_background"]["ok"])
        self.assertTrue(runtime["zero_engine"]["ok"])
        self.assertTrue(runtime["zero_engine_background"]["ok"])
        self.assertTrue(runtime["control_workflows"]["ok"])
        self.assertTrue(runtime["capability_control_map"]["ok"])
        self.assertTrue(runtime["evolution"]["ok"])
        self.assertTrue(runtime["source_evolution"]["ok"])

        saved = zero_ai_runtime_status(str(self.base))
        self.assertIn("continuity_governance_background", saved)
        self.assertIn("autonomy", saved)
        self.assertIn("zero_engine", saved)
        self.assertIn("control_workflows", saved)
        self.assertIn("capability_control_map", saved)
        self.assertIn("evolution", saved)
        self.assertIn("self_derivation", saved)
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

    def test_runtime_run_processes_communications_and_calendar_background(self) -> None:
        zero_ai_identity(str(self.base))
        zero_ai_self_continuity_update(str(self.base))
        draft = communications_draft_add(str(self.base), "vincent@example.com", "ship now")["draft"]
        approval = communications_send_request(str(self.base), draft["id"])
        approval_decide(str(self.base), approval["approval"]["id"], True)
        calendar_reminder_add(str(self.base), "review zero ai", "2026-03-18T09:00:00+00:00")

        runtime = zero_ai_runtime_run(str(self.base))

        self.assertTrue(runtime["ok"])
        self.assertIn("communications_background", runtime)
        self.assertIn("calendar_time_background", runtime)
        self.assertTrue(runtime["communications_background"]["ok"])
        self.assertTrue(runtime["calendar_time_background"]["ok"])

    def test_runtime_run_revalidates_ready_self_derivation_strategies_when_stable(self) -> None:
        from zero_os.self_derivation_engine import self_derivation_status
        from zero_os.zero_ai_pressure_harness import pressure_harness_run

        zero_ai_identity(str(self.base))
        zero_ai_self_continuity_update(str(self.base))
        pressure_harness_run(str(self.base))

        derivation_dir = self.base / ".zero_os" / "assistant" / "self_derivation"
        derivation_dir.mkdir(parents=True, exist_ok=True)
        seed_record = {
            "strategy": "verification_first",
            "planner_version": _current_planner_version(),
            "code_version": _current_strategy_code_version(),
            "planner_version_history": [_current_planner_version()],
            "code_version_history": [_current_strategy_code_version()],
            "run_count": 5,
            "success_count": 4,
            "failure_count": 1,
            "recovery_count": 1,
            "contradiction_hold_count": 0,
            "reroute_count": 1,
            "success_rate": 0.8,
            "failure_rate": 0.2,
            "recovery_rate": 0.2,
            "contradiction_hold_rate": 0.0,
            "average_outcome_quality": 0.86,
            "resilience_score": 0.82,
            "last_run_utc": datetime.now(timezone.utc).isoformat(),
            "last_branch_shape": {"pattern_signature": "verify -> prepare -> mutate"},
            "last_condition_profile": {
                "subsystem_surface": "browser_mutate_surface",
                "structure_family": "interactive_browser_flow",
                "semantic_goal": "mutate_resource",
                "target_families": ["interaction_surface", "remote_source"],
                "target_types": ["urls"],
                "risk_level": "medium",
                "execution_mode": "safe",
                "strategy_mode": "safe",
            },
            "last_outcome": {"ok": True},
        }
        canary_plan = _strategy_canary_plan("verification_first", seed_record)
        canary_condition = _strategy_condition_profile(canary_plan)
        canary_shape = _branch_shape_profile(canary_plan)
        seed_record["condition_profiles"] = {
            canary_condition["signature"]: {
                "condition_profile": {key: value for key, value in canary_condition.items() if key != "signature"},
                "run_count": 2,
                "success_count": 2,
                "failure_count": 0,
                "recovery_count": 0,
                "success_rate": 1.0,
                "failure_rate": 0.0,
                "recovery_rate": 0.0,
                "last_seen_utc": datetime.now(timezone.utc).isoformat(),
                "planner_version": _current_planner_version(),
                "code_version": _current_strategy_code_version(),
            }
        }
        seed_record["shape_profiles"] = {
            canary_shape["signature"]: {
                "branch_shape": {key: value for key, value in canary_shape.items() if key != "signature"},
                "run_count": 2,
                "success_count": 2,
                "failure_count": 0,
                "recovery_count": 0,
                "success_rate": 1.0,
                "failure_rate": 0.0,
                "recovery_rate": 0.0,
                "average_outcome_quality": 0.9,
                "last_seen_utc": datetime.now(timezone.utc).isoformat(),
                "planner_version": _current_planner_version(),
                "code_version": _current_strategy_code_version(),
            }
        }
        (derivation_dir / "memory.json").write_text(
            json.dumps(
                {
                    "schema_version": 2,
                    "patterns": {},
                    "knowledge": [],
                    "strategy_outcomes": {},
                    "quarantined_strategy_outcomes": {"verification_first": seed_record},
                    "meta_rules": [],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        before = self_derivation_status(str(self.base))
        self.assertEqual(1, int(before["revalidation_ready_count"]))

        runtime = zero_ai_runtime_run(str(self.base))

        self.assertTrue(runtime["ok"])
        self.assertIn("self_derivation_background", runtime)
        self.assertTrue(runtime["self_derivation_background"]["ok"])
        self.assertTrue(runtime["self_derivation_background"]["ran"])
        self.assertEqual(1, int(runtime["self_derivation_background"]["restored_count"]))
        self.assertTrue(runtime["runtime_checks"]["self_derivation_background"])
        self.assertEqual(1, int(runtime["self_derivation"]["strategy_outcome_count"]))
        self.assertEqual(0, int(runtime["self_derivation"]["quarantined_strategy_count"]))

    def test_runtime_run_flushes_cached_state_writes(self) -> None:
        zero_ai_identity(str(self.base))

        runtime = zero_ai_runtime_run(str(self.base))
        cache_status = state_cache_status()

        self.assertTrue(runtime["ok"])
        self.assertEqual(0, int(runtime["state_cache"]["pending_write_count"]))
        self.assertEqual(0, int(cache_status["pending_write_count"]))
        self.assertTrue((self.base / ".zero_os" / "runtime" / "phase_runtime_status.json").exists())

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
