import json
import subprocess
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
from zero_os.fast_path_cache import clear_fast_path_cache
from zero_os.phase_runtime import zero_ai_runtime_run
from zero_os.self_continuity import zero_ai_self_continuity_update
from zero_os.task_executor import run_task
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
        self.assertIn("approval_status_cache_hit", status["summary"])
        self.assertIn("benchmark_remediation_status_cache_hit", status["summary"])
        self.assertIn("benchmark_status_cache_hit_count", status["summary"])
        self.assertIn("benchmark_status_cache_total_count", status["summary"])
        self.assertIn("benchmark_dashboard_status_cache_hit", status["summary"])
        self.assertIn("benchmark_gate_status_cache_hit", status["summary"])
        self.assertIn("benchmark_alert_routes_status_cache_hit", status["summary"])
        self.assertIn("communications_status_cache_hit", status["summary"])
        self.assertIn("calendar_time_status_cache_hit", status["summary"])
        self.assertIn("local_control_cache_hit_count", status["summary"])
        self.assertIn("local_control_cache_total_count", status["summary"])
        self.assertIn("control_workflows_status_cache_hit", status["summary"])
        self.assertIn("general_agent_status_cache_hit", status["summary"])
        self.assertIn("capability_expansion_protocol_status_cache_hit", status["summary"])
        self.assertIn("domain_pack_factory_status_cache_hit", status["summary"])
        self.assertIn("workflow_status_cache_hit_count", status["summary"])
        self.assertIn("workflow_status_cache_total_count", status["summary"])
        self.assertIn("governor_call", status["summary"])
        self.assertIn("governor_mode", status["summary"])
        self.assertIn("governor_summary", status["summary"])
        self.assertIn("governor_blocking_factors", status["summary"])

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
        self.assertEqual("autonomous", capabilities["self_derivation_engine"]["control_level"])
        self.assertEqual("autonomous", capabilities["general_agent_orchestrator"]["control_level"])
        self.assertEqual("autonomous", capabilities["capability_expansion_protocol"]["control_level"])
        self.assertEqual("autonomous", capabilities["domain_pack_factory"]["control_level"])
        self.assertEqual("autonomous", capabilities["communications_lane"]["control_level"])
        self.assertEqual("autonomous", capabilities["calendar_time_lane"]["control_level"])
        self.assertEqual("autonomous", capabilities["approval_gate_state"]["control_level"])
        self.assertEqual("autonomous", capabilities["benchmark_remediation_lane"]["control_level"])
        self.assertIn("decision_governor", capabilities)
        self.assertEqual("autonomous", capabilities["browser_control"]["control_level"])
        self.assertEqual("autonomous", capabilities["store_installation"]["control_level"])
        self.assertEqual("autonomous", capabilities["recovery_restore"]["control_level"])
        self.assertEqual("autonomous", capabilities["high_risk_self_repair"]["control_level"])
        self.assertEqual("forbidden", capabilities["identity_core_rewrite"]["control_level"])

    def test_capability_map_keeps_approval_lane_active_when_queue_is_empty(self) -> None:
        self._prime_runtime()

        with patch("zero_os.phase_runtime._pid_alive", return_value=True):
            status = zero_ai_capability_map_status(str(self.base))

        capabilities = {item["key"]: item for item in status["capabilities"]}
        approval_lane = capabilities["approval_gate_state"]
        self.assertTrue(approval_lane["ready"])
        self.assertTrue(approval_lane["active"])
        self.assertEqual(0, approval_lane["evidence"]["pending_count"])

    def test_capability_map_writes_status_file(self) -> None:
        self._prime_runtime()
        run_task(str(self.base), "browser status")

        with patch("zero_os.phase_runtime._pid_alive", return_value=True):
            status = zero_ai_capability_map_status(str(self.base))

        path = Path(status["map_path"])
        self.assertTrue(path.exists())
        persisted = json.loads(path.read_text(encoding="utf-8"))
        self.assertIn("highest_value_steps", persisted)
        self.assertIn("general_agent", persisted)
        self.assertIn("capability_expansion_protocol", persisted)
        self.assertIn("domain_pack_factory", persisted)
        self.assertEqual(status["summary"]["approval_gated_count"], persisted["summary"]["approval_gated_count"])
        self.assertIn("planner_feedback_history_count", status["summary"])
        self.assertIn("planner_route_quality_score", status["summary"])
        self.assertIn("planner_feedback_worst_route_variant", status["summary"])
        self.assertIn("self_derivation_strategy_freshness_score", status["summary"])
        self.assertIn("self_derivation_version_mismatch_count", status["summary"])
        self.assertIn("self_derivation_quarantined_strategy_count", status["summary"])
        self.assertIn("self_derivation_revalidation_ready_count", status["summary"])
        self.assertIn("self_derivation_runtime_revalidation_state", status["summary"])
        self.assertIn("self_derivation_runtime_revalidation_restored_count", status["summary"])
        self.assertIn("self_derivation_runtime_revalidation_reason", status["summary"])
        self.assertIn("self_derivation_strategy_trend_direction", status["summary"])
        self.assertIn("self_derivation_strategy_history_point_count", status["summary"])
        self.assertIn("internet_surface_cache_hit_count", status["summary"])
        self.assertIn("internet_surface_cache_total_count", status["summary"])
        self.assertIn("internet_browser_session_cache_hit", status["summary"])
        self.assertIn("internet_browser_dom_cache_hit", status["summary"])
        self.assertIn("internet_api_profiles_cache_hit", status["summary"])
        self.assertIn("internet_github_cache_hit", status["summary"])
        self.assertIn("approval_status_cache_hit", status["summary"])
        self.assertIn("benchmark_remediation_status_cache_hit", status["summary"])
        self.assertIn("benchmark_status_cache_hit_count", status["summary"])
        self.assertIn("benchmark_status_cache_total_count", status["summary"])
        self.assertIn("benchmark_dashboard_status_cache_hit", status["summary"])
        self.assertIn("benchmark_gate_status_cache_hit", status["summary"])
        self.assertIn("benchmark_alert_routes_status_cache_hit", status["summary"])
        self.assertIn("communications_status_cache_hit", status["summary"])
        self.assertIn("calendar_time_status_cache_hit", status["summary"])
        self.assertIn("local_control_cache_hit_count", status["summary"])
        self.assertIn("local_control_cache_total_count", status["summary"])
        self.assertIn("control_workflows_status_cache_hit", status["summary"])
        self.assertIn("general_agent_status_cache_hit", status["summary"])
        self.assertIn("capability_expansion_protocol_status_cache_hit", status["summary"])
        self.assertIn("domain_pack_factory_status_cache_hit", status["summary"])
        self.assertIn("workflow_status_cache_hit_count", status["summary"])
        self.assertIn("workflow_status_cache_total_count", status["summary"])
        capabilities = {item["key"]: item for item in status["capabilities"]}
        self.assertGreaterEqual(capabilities["pressure_harness"]["evidence"]["planner_feedback_history_count"], 1)
        self.assertIn("self_derivation_engine", capabilities)
        self.assertIn("approval_gate_state", capabilities)
        self.assertIn("benchmark_remediation_lane", capabilities)
        self.assertIn("internet_surfaces", capabilities)
        self.assertIn("strategy_freshness_score", capabilities["self_derivation_engine"]["evidence"])
        self.assertIn("version_mismatch_count", capabilities["self_derivation_engine"]["evidence"])
        self.assertIn("quarantined_strategy_count", capabilities["self_derivation_engine"]["evidence"])
        self.assertIn("revalidation_ready_count", capabilities["self_derivation_engine"]["evidence"])
        self.assertIn("runtime_revalidation_state", capabilities["self_derivation_engine"]["evidence"])
        self.assertIn("runtime_revalidation_restored_count", capabilities["self_derivation_engine"]["evidence"])
        self.assertIn("runtime_revalidation_reason", capabilities["self_derivation_engine"]["evidence"])
        self.assertIn("strategy_history_points", capabilities["self_derivation_engine"]["evidence"])
        self.assertIn("surface_cache_hit_count", capabilities["internet_surfaces"]["evidence"])
        self.assertIn("status_cache_hit", capabilities["approval_gate_state"]["evidence"])
        self.assertIn("status_cache_hit", capabilities["benchmark_remediation_lane"]["evidence"])
        self.assertIn("status_cache_hit", capabilities["general_agent_orchestrator"]["evidence"])
        self.assertIn("status_cache_hit", capabilities["capability_expansion_protocol"]["evidence"])
        self.assertIn("status_cache_hit", capabilities["domain_pack_factory"]["evidence"])
        self.assertIn("workflow_status_cache_hit", capabilities["browser_control"]["evidence"])
        self.assertIn("summary", capabilities["decision_governor"]["evidence"])

    def test_capability_map_uses_fast_path_when_inputs_are_unchanged(self) -> None:
        self._prime_runtime()
        first = zero_ai_capability_map_status(str(self.base))

        with patch("zero_os.zero_ai_capability_map._build_zero_ai_capability_map_status", side_effect=AssertionError("should use cache")):
            second = zero_ai_capability_map_status(str(self.base))

        self.assertFalse(first["fast_path_cache"]["hit"])
        self.assertTrue(second["fast_path_cache"]["hit"])
        self.assertEqual(first["summary"]["autonomous_count"], second["summary"]["autonomous_count"])

    def test_capability_map_invalidates_when_control_workflows_artifact_changes(self) -> None:
        self._prime_runtime()
        first = zero_ai_capability_map_status(str(self.base))
        self.assertFalse(first["fast_path_cache"]["hit"])

        workflows_path = self.base / ".zero_os" / "assistant" / "control_workflows.json"
        workflows_path.parent.mkdir(parents=True, exist_ok=True)
        workflows_path.write_text(
            json.dumps(
                {
                    "ok": True,
                    "summary": {"ready_count": 4},
                    "lanes": {
                        "recovery": {
                            "trusted_snapshot_count": 1,
                            "quarantined_snapshot_count": 0,
                            "active_incompatible_snapshot_count": 0,
                        }
                    },
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        clear_fast_path_cache(namespace="zero_ai_capability_map_status")
        sentinel = {"ok": True, "summary": {"recovery_trusted_snapshot_count": 999}}
        with patch("zero_os.zero_ai_capability_map._build_zero_ai_capability_map_status", return_value=sentinel):
            second = zero_ai_capability_map_status(str(self.base))

        self.assertFalse(second["fast_path_cache"]["hit"])
        self.assertEqual(999, second["summary"]["recovery_trusted_snapshot_count"])

    def test_capability_map_surfaces_blocked_governor_summary(self) -> None:
        self._prime_runtime()
        request_approval(str(self.base), "browser_action", "need approval", {"run_id": "run-1", "target": {"url": "https://example.com"}})

        with patch("zero_os.phase_runtime._pid_alive", return_value=True):
            zero_ai_runtime_run(str(self.base))
            status = zero_ai_capability_map_status(str(self.base))

        self.assertEqual("wait_for_user", status["summary"]["governor_call"])
        self.assertIn("approval", status["summary"]["governor_summary"])
        self.assertGreaterEqual(status["summary"]["governor_blocking_factor_count"], 1)

    def test_capability_map_bootstraps_benchmark_history_without_repo_root_on_sys_path(self) -> None:
        self._prime_runtime()
        script = (
            "import json, sys\n"
            "from pathlib import Path\n"
            "repo = Path(sys.argv[1]).resolve()\n"
            "cwd = Path(sys.argv[2]).resolve()\n"
            "src = repo / 'src'\n"
            "repo_str = str(repo)\n"
            "src_str = str(src)\n"
            "sys.path = [p for p in sys.path if p not in {repo_str, src_str}]\n"
            "sys.path.insert(0, src_str)\n"
            "from zero_os.zero_ai_capability_map import zero_ai_capability_map_status\n"
            "status = zero_ai_capability_map_status(str(cwd))\n"
            "print(json.dumps({'ok': status.get('ok', False)}))\n"
            "raise SystemExit(0 if status.get('ok', False) else 1)\n"
        )

        completed = subprocess.run(
            [sys.executable, "-c", script, str(ROOT), str(self.base)],
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(0, completed.returncode, msg=completed.stderr or completed.stdout)
        self.assertEqual(True, json.loads(completed.stdout)["ok"])


if __name__ == "__main__":
    unittest.main()
