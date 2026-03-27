import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from zero_os.world_class_readiness import world_class_readiness_status


class WorldClassReadinessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="world_class_readiness_")
        self.base = Path(self.tempdir)
        (self.base / ".zero_os").mkdir(parents=True, exist_ok=True)
        (self.base / ".zero_os" / "state.json").write_text("{}\n", encoding="utf-8")

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_readiness_surfaces_top_gap_and_score(self) -> None:
        with patch(
            "zero_os.world_class_readiness.zero_ai_capability_map_status",
            return_value={"summary": {"autonomous_surface_score": 80.0, "active_autonomous_surface_score": 70.0, "approval_gated_count": 1, "forbidden_count": 2, "governor_call": "observe", "governor_mode": "normal", "governor_summary": "governor gate: observe", "recovery_trusted_snapshot_count": 1, "recovery_quarantined_snapshot_count": 0, "recovery_active_incompatible_snapshot_count": 0}},
        ), patch(
            "zero_os.world_class_readiness.maintenance_status",
            return_value={"next_action": {"reason": "stable"}},
        ), patch(
            "zero_os.world_class_readiness.internet_capability_status",
            return_value={"summary": {"internet_ready": True, "connected_surface_count": 0}, "browser": {"connected": False}, "api_profiles": {"count": 0}},
        ), patch(
            "zero_os.zero_ai_pressure_harness.pressure_harness_status",
            return_value={"missing": False, "overall_score": 100.0, "failed_count": 0},
        ):
            status = world_class_readiness_status(str(self.base))

        self.assertTrue(status["ok"])
        self.assertIn("overall_score", status)
        self.assertEqual("approval_gated_capabilities", status["top_gap"])
        self.assertFalse(status["world_class_now"])
        self.assertEqual("observe", status["decision_governor"]["call"])
        self.assertTrue(status["decision_governor"]["act_now_allowed"])

    def test_forbidden_surfaces_do_not_count_as_control_gap(self) -> None:
        with patch(
            "zero_os.world_class_readiness.zero_ai_capability_map_status",
            return_value={"summary": {"autonomous_surface_score": 100.0, "active_autonomous_surface_score": 100.0, "autonomous_count": 12, "active_autonomous_count": 12, "approval_gated_count": 0, "forbidden_count": 3, "planner_feedback_history_count": 0, "planner_route_quality_score": 100.0, "governor_call": "observe", "governor_mode": "normal", "governor_summary": "governor gate: observe", "recovery_trusted_snapshot_count": 1, "recovery_quarantined_snapshot_count": 0, "recovery_active_incompatible_snapshot_count": 0}},
        ), patch(
            "zero_os.world_class_readiness.maintenance_status",
            return_value={"next_action": {"reason": "stable"}},
        ), patch(
            "zero_os.world_class_readiness.internet_capability_status",
            return_value={"summary": {"internet_ready": True, "connected_surface_count": 2}, "browser": {"connected": True}, "api_profiles": {"count": 1}},
        ), patch(
            "zero_os.zero_ai_pressure_harness.pressure_harness_status",
            return_value={"missing": False, "overall_score": 100.0, "failed_count": 0},
        ):
            status = world_class_readiness_status(str(self.base))

        self.assertEqual(100.0, status["overall_score"])
        self.assertEqual("none", status["top_gap"])
        self.assertTrue(status["world_class_now"])
        self.assertEqual(3, status["inputs"]["forbidden_surface_count"])
        self.assertEqual(100.0, status["lanes"]["control"]["score"])
        self.assertEqual("observe", status["inputs"]["governor_call"])

    def test_readiness_surfaces_planner_route_drift_when_history_is_weak(self) -> None:
        with patch(
            "zero_os.world_class_readiness.zero_ai_capability_map_status",
            return_value={
                "summary": {
                    "autonomous_surface_score": 100.0,
                    "active_autonomous_surface_score": 100.0,
                    "autonomous_count": 12,
                    "active_autonomous_count": 12,
                    "approval_gated_count": 0,
                    "forbidden_count": 3,
                    "planner_feedback_history_count": 8,
                    "planner_route_quality_score": 72.5,
                    "planner_feedback_worst_route": "web",
                    "planner_feedback_worst_route_variant": "browser_click",
                    "planner_feedback_target_drop_rate": 0.2,
                    "planner_feedback_contradiction_hold_rate": 0.35,
                    "governor_call": "observe",
                    "governor_mode": "normal",
                    "governor_summary": "governor gate: observe",
                    "recovery_trusted_snapshot_count": 1,
                    "recovery_quarantined_snapshot_count": 0,
                    "recovery_active_incompatible_snapshot_count": 0,
                }
            },
        ), patch(
            "zero_os.world_class_readiness.maintenance_status",
            return_value={"next_action": {"reason": "stable"}},
        ), patch(
            "zero_os.world_class_readiness.internet_capability_status",
            return_value={"summary": {"internet_ready": True, "connected_surface_count": 2}, "browser": {"connected": True}, "api_profiles": {"count": 1}},
        ), patch(
            "zero_os.zero_ai_pressure_harness.pressure_harness_status",
            return_value={"missing": False, "overall_score": 100.0, "failed_count": 0},
        ):
            status = world_class_readiness_status(str(self.base))

        self.assertEqual("planner_route_drift", status["top_gap"])
        self.assertEqual("web", status["inputs"]["planner_feedback_worst_route"])
        self.assertEqual("browser_click", status["inputs"]["planner_feedback_worst_route_variant"])
        self.assertLess(status["lanes"]["evidence"]["score"], 100.0)

    def test_readiness_surfaces_strategy_memory_version_drift(self) -> None:
        with patch(
            "zero_os.world_class_readiness.zero_ai_capability_map_status",
            return_value={
                "summary": {
                    "autonomous_surface_score": 100.0,
                    "active_autonomous_surface_score": 100.0,
                    "autonomous_count": 12,
                    "active_autonomous_count": 12,
                    "approval_gated_count": 0,
                    "forbidden_count": 3,
                    "planner_feedback_history_count": 4,
                    "planner_route_quality_score": 100.0,
                    "planner_feedback_worst_route": "",
                    "planner_feedback_target_drop_rate": 0.0,
                    "planner_feedback_contradiction_hold_rate": 0.0,
                    "governor_call": "observe",
                    "governor_mode": "normal",
                    "governor_summary": "governor gate: observe",
                    "recovery_trusted_snapshot_count": 1,
                    "recovery_quarantined_snapshot_count": 0,
                    "recovery_active_incompatible_snapshot_count": 0,
                    "self_derivation_strategy_freshness_score": 0.88,
                    "self_derivation_stale_strategy_count": 0,
                    "self_derivation_version_mismatch_count": 2,
                    "self_derivation_top_recovery_profile": "proven",
                }
            },
        ), patch(
            "zero_os.world_class_readiness.maintenance_status",
            return_value={"next_action": {"reason": "stable"}},
        ), patch(
            "zero_os.world_class_readiness.internet_capability_status",
            return_value={"summary": {"internet_ready": True, "connected_surface_count": 2}, "browser": {"connected": True}, "api_profiles": {"count": 1}},
        ), patch(
            "zero_os.zero_ai_pressure_harness.pressure_harness_status",
            return_value={"missing": False, "overall_score": 100.0, "failed_count": 0},
        ):
            status = world_class_readiness_status(str(self.base))

        self.assertEqual("strategy_memory_version_drift", status["top_gap"])
        self.assertEqual(2, status["inputs"]["self_derivation_version_mismatch_count"])
        self.assertIn("self_derivation_strategy_trend_direction", status["inputs"])

    def test_readiness_surfaces_blocked_governor_summary(self) -> None:
        with patch(
            "zero_os.world_class_readiness.zero_ai_capability_map_status",
            return_value={
                "summary": {
                    "autonomous_surface_score": 100.0,
                    "active_autonomous_surface_score": 100.0,
                    "autonomous_count": 12,
                    "active_autonomous_count": 12,
                    "approval_gated_count": 0,
                    "forbidden_count": 3,
                    "planner_feedback_history_count": 0,
                    "planner_route_quality_score": 100.0,
                    "governor_call": "wait_for_user",
                    "governor_mode": "blocked",
                    "governor_reason": "human approval is required before further autonomous action",
                    "governor_blocking_factors": ["1 approval item(s) pending"],
                    "governor_summary": "governor gate: wait_for_user (human approval is required before further autonomous action) blockers=1 approval item(s) pending",
                    "recovery_trusted_snapshot_count": 1,
                    "recovery_quarantined_snapshot_count": 0,
                    "recovery_active_incompatible_snapshot_count": 0,
                }
            },
        ), patch(
            "zero_os.world_class_readiness.maintenance_status",
            return_value={"next_action": {"reason": "stable"}},
        ), patch(
            "zero_os.world_class_readiness.internet_capability_status",
            return_value={"summary": {"internet_ready": True, "connected_surface_count": 2}, "browser": {"connected": True}, "api_profiles": {"count": 1}},
        ), patch(
            "zero_os.zero_ai_pressure_harness.pressure_harness_status",
            return_value={"missing": False, "overall_score": 100.0, "failed_count": 0},
        ):
            status = world_class_readiness_status(str(self.base))

        self.assertEqual("wait_for_user", status["decision_governor"]["call"])
        self.assertFalse(status["decision_governor"]["act_now_allowed"])
        self.assertIn("approval", status["decision_governor"]["summary"])
        self.assertEqual(1, status["inputs"]["governor_blocking_factor_count"])

    def test_readiness_uses_fast_path_when_inputs_are_unchanged(self) -> None:
        first = world_class_readiness_status(str(self.base))

        with patch("zero_os.world_class_readiness._build_world_class_readiness_status", side_effect=AssertionError("should use cache")):
            second = world_class_readiness_status(str(self.base))

        self.assertFalse(first["fast_path_cache"]["hit"])
        self.assertTrue(second["fast_path_cache"]["hit"])
        self.assertEqual(first["overall_score"], second["overall_score"])
