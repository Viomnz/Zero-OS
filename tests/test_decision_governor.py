import shutil
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from zero_os.decision_governor import governor_decide
from zero_os.world_model import build_world_model


class DecisionGovernorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_governor_")
        self.base = Path(self.tempdir)

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_governor_waits_for_user_when_approvals_are_pending(self) -> None:
        model = build_world_model(
            str(self.base),
            sources={
                "runtime": {"runtime_ready": True, "missing": False, "runtime_score": 100.0},
                "runtime_loop": {"enabled": True},
                "runtime_agent": {"installed": True, "running": True},
                "continuity": {
                    "continuity": {"same_system": True, "continuity_score": 100.0},
                    "contradiction_detection": {"has_contradiction": False},
                },
                "pressure": {"missing": False, "overall_score": 100.0},
                "approvals": {"pending_count": 1},
                "jobs": {"count": 0},
            },
        )

        decision = governor_decide(str(self.base), world_model=model)

        self.assertEqual("wait_for_user", decision["call"])
        self.assertEqual("blocked", decision["mode"])

    def test_governor_prefers_runtime_when_runtime_is_missing(self) -> None:
        model = build_world_model(
            str(self.base),
            sources={
                "runtime": {"runtime_ready": False, "missing": True, "runtime_score": 0.0},
                "runtime_loop": {"enabled": False},
                "runtime_agent": {"installed": False, "running": False},
                "continuity": {
                    "continuity": {"same_system": True, "continuity_score": 100.0},
                    "contradiction_detection": {"has_contradiction": False},
                },
                "pressure": {"missing": False, "overall_score": 100.0},
                "approvals": {"pending_count": 0},
                "jobs": {"count": 0},
            },
        )

        decision = governor_decide(str(self.base), world_model=model)

        self.assertEqual("run_runtime", decision["call"])
        self.assertEqual("safe", decision["mode"])

    def test_governor_selects_revalidation_when_stable_and_ready(self) -> None:
        model = build_world_model(
            str(self.base),
            sources={
                "runtime": {"runtime_ready": True, "missing": False, "runtime_score": 100.0},
                "runtime_loop": {"enabled": True},
                "runtime_agent": {"installed": True, "running": True},
                "continuity": {
                    "continuity": {"same_system": True, "continuity_score": 100.0},
                    "contradiction_detection": {"has_contradiction": False},
                },
                "pressure": {"missing": False, "overall_score": 100.0},
                "self_derivation": {"ok": True, "revalidation_ready_count": 2},
                "approvals": {"pending_count": 0},
                "jobs": {"count": 0},
            },
        )

        decision = governor_decide(str(self.base), world_model=model)

        self.assertEqual("self_derivation_revalidate", decision["call"])
        self.assertEqual("guarded", decision["mode"])

    def test_governor_requires_recovery_stabilization_when_no_compatible_snapshot_exists(self) -> None:
        model = build_world_model(
            str(self.base),
            sources={
                "runtime": {"runtime_ready": True, "missing": False, "runtime_score": 100.0},
                "runtime_loop": {"enabled": True},
                "runtime_agent": {"installed": True, "running": True},
                "continuity": {
                    "continuity": {"same_system": True, "continuity_score": 100.0},
                    "contradiction_detection": {"has_contradiction": False},
                },
                "pressure": {"missing": False, "overall_score": 100.0},
                "recovery": {"snapshot_count": 2, "compatible_count": 0, "latest_compatible_snapshot_id": ""},
                "approvals": {"pending_count": 0},
                "jobs": {"count": 0},
            },
        )

        decision = governor_decide(str(self.base), world_model=model)

        self.assertEqual("stabilize_recovery", decision["call"])
        self.assertEqual("safe", decision["mode"])
        self.assertIn("latest compatible snapshot missing", decision["blocking_factors"])

    def test_governor_switches_to_code_fix_loop_when_code_workbench_is_ready(self) -> None:
        model = build_world_model(
            str(self.base),
            sources={
                "runtime": {"runtime_ready": True, "missing": False, "runtime_score": 100.0},
                "runtime_loop": {"enabled": True},
                "runtime_agent": {"installed": True, "running": True},
                "continuity": {
                    "continuity": {"same_system": True, "continuity_score": 100.0},
                    "contradiction_detection": {"has_contradiction": False},
                },
                "pressure": {"missing": False, "overall_score": 100.0},
                "code_workbench": {
                    "workspace_ready": True,
                    "requested_code_mutation": True,
                    "scope_ready": True,
                    "verification_ready": True,
                    "verification_surface_ready": True,
                    "dirty_in_scope_count": 0,
                    "source_canary_ready": True,
                    "target_file_count": 1,
                    "in_scope_count": 1,
                    "out_of_scope_count": 0,
                    "missing_in_scope_count": 0,
                    "ready": True,
                },
                "approvals": {"pending_count": 0},
                "jobs": {"count": 0},
            },
        )

        decision = governor_decide(str(self.base), world_model=model)

        self.assertEqual("run_code_fix_loop", decision["call"])
        self.assertEqual("guarded", decision["mode"])

    def test_governor_waits_for_clean_scope_when_in_scope_targets_are_already_dirty(self) -> None:
        model = build_world_model(
            str(self.base),
            sources={
                "runtime": {"runtime_ready": True, "missing": False, "runtime_score": 100.0},
                "runtime_loop": {"enabled": True},
                "runtime_agent": {"installed": True, "running": True},
                "continuity": {
                    "continuity": {"same_system": True, "continuity_score": 100.0},
                    "contradiction_detection": {"has_contradiction": False},
                },
                "pressure": {"missing": False, "overall_score": 100.0},
                "code_workbench": {
                    "workspace_ready": True,
                    "requested_code_mutation": True,
                    "scope_ready": True,
                    "verification_ready": True,
                    "verification_surface_ready": True,
                    "dirty_in_scope_count": 1,
                    "target_file_count": 1,
                    "in_scope_count": 1,
                    "out_of_scope_count": 0,
                    "missing_in_scope_count": 0,
                    "ready": True,
                },
                "approvals": {"pending_count": 0},
                "jobs": {"count": 0},
            },
        )

        decision = governor_decide(str(self.base), world_model=model)

        self.assertEqual("wait_for_clean_scope", decision["call"])
        self.assertIn("1 in-scope code target(s) already dirty", decision["blocking_factors"])

    def test_governor_routes_to_code_canary_when_verification_surface_is_weak(self) -> None:
        model = build_world_model(
            str(self.base),
            sources={
                "runtime": {"runtime_ready": True, "missing": False, "runtime_score": 100.0},
                "runtime_loop": {"enabled": True},
                "runtime_agent": {"installed": True, "running": True},
                "continuity": {
                    "continuity": {"same_system": True, "continuity_score": 100.0},
                    "contradiction_detection": {"has_contradiction": False},
                },
                "pressure": {"missing": False, "overall_score": 100.0},
                "code_workbench": {
                    "workspace_ready": True,
                    "requested_code_mutation": True,
                    "scope_ready": True,
                    "verification_ready": True,
                    "verification_surface_ready": False,
                    "dirty_in_scope_count": 0,
                    "source_canary_ready": True,
                    "target_file_count": 1,
                    "in_scope_count": 1,
                    "out_of_scope_count": 0,
                    "missing_in_scope_count": 0,
                    "ready": True,
                },
                "approvals": {"pending_count": 0},
                "jobs": {"count": 0},
            },
        )

        decision = governor_decide(str(self.base), world_model=model)

        self.assertEqual("run_code_canary", decision["call"])
        self.assertEqual("guarded", decision["mode"])

    def test_governor_progresses_goal_when_world_model_is_stable(self) -> None:
        model = build_world_model(
            str(self.base),
            sources={
                "runtime": {"runtime_ready": True, "missing": False, "runtime_score": 100.0},
                "runtime_loop": {"enabled": True},
                "runtime_agent": {"installed": True, "running": True},
                "continuity": {
                    "continuity": {"same_system": True, "continuity_score": 100.0},
                    "contradiction_detection": {"has_contradiction": False},
                },
                "pressure": {"missing": False, "overall_score": 100.0},
                "goal_memory": {
                    "goal_count": 1,
                    "open_count": 1,
                    "blocked_count": 0,
                    "current_goal_title": "Fix planner drift",
                    "current_goal_next_action": "run goal loop",
                    "current_goal_requires_user": False,
                    "current_goal_state": "open",
                    "loop_enabled": True,
                    "loop_due_now": True,
                },
                "observation_stream": {"event_count": 0, "blocking_event_count": 0, "recent": []},
                "approvals": {"pending_count": 0},
                "jobs": {"count": 0},
            },
        )

        decision = governor_decide(str(self.base), world_model=model)

        self.assertEqual("goal_progress", decision["call"])
        self.assertEqual("normal", decision["mode"])

    def test_governor_requests_runtime_refresh_when_world_model_is_stale(self) -> None:
        model = build_world_model(
            str(self.base),
            sources={
                "runtime": {"runtime_ready": True, "missing": False, "runtime_score": 100.0},
                "runtime_loop": {"enabled": True},
                "runtime_agent": {"installed": True, "running": True},
                "continuity": {
                    "continuity": {"same_system": True, "continuity_score": 100.0},
                    "contradiction_detection": {"has_contradiction": False},
                },
                "pressure": {"missing": False, "overall_score": 100.0},
                "approvals": {"pending_count": 0},
                "jobs": {"count": 0},
            },
        )
        model["stale"] = True
        model["fresh_enough"] = False
        model["stale_domains"] = ["runtime"]

        decision = governor_decide(str(self.base), world_model=model)

        self.assertEqual("run_runtime", decision["call"])
        self.assertEqual("safe", decision["mode"])
        self.assertIn("runtime", decision["blocking_factors"])


if __name__ == "__main__":
    unittest.main()
