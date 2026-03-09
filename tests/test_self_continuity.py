import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from zero_os.self_continuity import (
    zero_ai_continuity_checkpoint_create,
    zero_ai_continuity_checkpoint_status,
    zero_ai_continuity_governance_auto_apply,
    zero_ai_continuity_governance_auto_status,
    zero_ai_continuity_governance_run,
    zero_ai_continuity_governance_set,
    zero_ai_continuity_governance_status,
    zero_ai_continuity_governance_tick,
    zero_ai_continuity_governor_apply,
    zero_ai_continuity_governor_check,
    zero_ai_continuity_governor_status,
    zero_ai_continuity_policy_auto_apply,
    zero_ai_continuity_policy_auto_status,
    zero_ai_continuity_policy_set,
    zero_ai_continuity_policy_status,
    zero_ai_continuity_restore_last_safe,
    zero_ai_continuity_simulate,
    zero_ai_continuity_simulate_apply,
    zero_ai_self_continuity_status,
    zero_ai_self_continuity_update,
    zero_ai_self_inspect_refresh,
    zero_ai_self_repair_restore_continuity,
)
from zero_os.zero_ai_identity import zero_ai_identity


class ZeroAISelfContinuityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_ai_self_continuity_")
        self.base = Path(self.tempdir)

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_builds_persistent_self_reference_state(self) -> None:
        zero_ai_identity(str(self.base))
        out = zero_ai_self_continuity_status(str(self.base))
        self.assertTrue(out["ok"])
        self.assertEqual("zero-ai-core", out["system"]["persistent_self_id"])
        self.assertTrue(out["continuity"]["same_system"])

    def test_tracks_recursive_state_updates(self) -> None:
        zero_ai_identity(str(self.base))
        first = zero_ai_self_continuity_update(str(self.base))
        second = zero_ai_self_continuity_update(str(self.base))
        self.assertGreater(
            second["recursive_state_tracking"]["state_versions"],
            first["recursive_state_tracking"]["state_versions"],
        )
        self.assertGreaterEqual(second["history_events"], 2)

    def test_detects_identity_contradiction(self) -> None:
        zero_ai_identity(str(self.base))
        snapshot = self.base / ".zero_os" / "runtime" / "zero_ai_identity_snapshot.json"
        payload = json.loads(snapshot.read_text(encoding="utf-8"))
        payload["classification"] = "self_mutation_engine"
        payload["is_rsi"] = True
        snapshot.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        out = zero_ai_self_continuity_update(str(self.base))
        self.assertTrue(out["contradiction_detection"]["has_contradiction"])
        self.assertIn("identity_classification_changed", out["contradiction_detection"]["issues"])
        self.assertIn("identity_claims_rsi", out["contradiction_detection"]["issues"])
        self.assertGreaterEqual(len(out["contradiction_detection"]["repair_suggestions"]), 1)
        self.assertGreaterEqual(out["policy_memory"]["contradiction_event_count"], 1)

    def test_self_inspect_refresh_returns_prioritized_steps(self) -> None:
        zero_ai_identity(str(self.base))
        out = zero_ai_self_inspect_refresh(str(self.base))
        self.assertTrue(out["ok"])
        self.assertGreaterEqual(len(out["highest_value_steps"]), 1)
        self.assertIn("next_priority", out)
        self.assertIn("repair_suggestions", out)

    def test_cross_session_policy_memory_persists(self) -> None:
        zero_ai_identity(str(self.base))
        snapshot = self.base / ".zero_os" / "runtime" / "zero_ai_identity_snapshot.json"
        payload = json.loads(snapshot.read_text(encoding="utf-8"))
        payload["is_rsi"] = True
        snapshot.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        zero_ai_self_continuity_update(str(self.base))
        status = zero_ai_self_continuity_status(str(self.base))
        self.assertGreaterEqual(status["policy_memory"]["contradiction_event_count"], 1)
        self.assertGreaterEqual(len(status["policy_memory"]["last_repair_suggestions"]), 1)

    def test_safe_state_auto_creates_checkpoint(self) -> None:
        zero_ai_identity(str(self.base))
        status = zero_ai_self_continuity_update(str(self.base))
        checkpoint_status = status["checkpoint_status"]
        self.assertGreaterEqual(checkpoint_status["checkpoint_count"], 1)
        self.assertTrue(checkpoint_status["latest_checkpoint"]["same_system"])

    def test_restore_last_safe_checkpoint_recovers_continuity(self) -> None:
        zero_ai_identity(str(self.base))
        zero_ai_self_continuity_update(str(self.base))

        snapshot = self.base / ".zero_os" / "runtime" / "zero_ai_identity_snapshot.json"
        payload = json.loads(snapshot.read_text(encoding="utf-8"))
        payload["classification"] = "unsafe_mutation_engine"
        payload["is_rsi"] = True
        snapshot.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

        broken = zero_ai_self_continuity_update(str(self.base))
        self.assertTrue(broken["contradiction_detection"]["has_contradiction"])

        restored = zero_ai_continuity_restore_last_safe(str(self.base))
        self.assertTrue(restored["ok"])
        self.assertTrue(restored["restored"])
        self.assertTrue(restored["self_continuity"]["continuity"]["same_system"])
        self.assertFalse(restored["self_continuity"]["contradiction_detection"]["has_contradiction"])

    def test_self_repair_restore_continuity_repairs_identity_and_state(self) -> None:
        zero_ai_identity(str(self.base))
        snapshot = self.base / ".zero_os" / "runtime" / "zero_ai_identity_snapshot.json"
        payload = json.loads(snapshot.read_text(encoding="utf-8"))
        payload["classification"] = "self_mutation_engine"
        payload["is_rsi"] = True
        payload["goals"]["constraints"] = []
        snapshot.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        state_path = self.base / ".zero_os" / "runtime" / "zero_ai_consciousness_state.json"
        bad_state = {
            "identity": {"name": "broken-ai", "classification": "broken", "is_rsi": True},
            "self_model": {
                "goals": [],
                "constraints": [],
                "confidence": 4.0,
                "uncertainty": -1.0,
                "continuity_index": 1,
            },
            "meta_awareness": {"introspection_cycles": 1, "last_quality_score": 10.0, "drift_signals": []},
        }
        state_path.write_text(json.dumps(bad_state, indent=2) + "\n", encoding="utf-8")

        repaired = zero_ai_self_repair_restore_continuity(str(self.base))
        self.assertTrue(repaired["continuity_restored"])
        self.assertGreaterEqual(len(repaired["repairs_applied"]), 1)
        status = zero_ai_self_continuity_status(str(self.base))
        self.assertFalse(status["contradiction_detection"]["has_contradiction"])

    def test_continuity_governor_allows_safe_live_state(self) -> None:
        zero_ai_identity(str(self.base))
        status = zero_ai_continuity_governor_status(str(self.base))
        self.assertTrue(status["ok"])
        self.assertEqual("balanced", status["active_policy_level"])
        check = zero_ai_continuity_governor_check(str(self.base))
        self.assertTrue(check["safe"])
        applied = zero_ai_continuity_governor_apply(str(self.base))
        self.assertTrue(applied["ok"])
        self.assertFalse(applied["blocked"])

    def test_continuity_policy_levels_can_be_set(self) -> None:
        zero_ai_identity(str(self.base))
        strict = zero_ai_continuity_policy_set(str(self.base), "strict")
        self.assertTrue(strict["ok"])
        self.assertEqual("strict", strict["active_policy_level"])
        research = zero_ai_continuity_policy_set(str(self.base), "research")
        self.assertTrue(research["ok"])
        self.assertEqual("research", research["active_policy_level"])
        status = zero_ai_continuity_policy_status(str(self.base))
        self.assertEqual("research", status["active_policy_level"])
        self.assertIn("balanced", status["available_policy_levels"])

    def test_auto_policy_status_defaults_to_balanced(self) -> None:
        zero_ai_identity(str(self.base))
        status = zero_ai_continuity_policy_auto_status(str(self.base))
        self.assertTrue(status["ok"])
        self.assertEqual("balanced", status["recommended_policy_level"])

    def test_auto_policy_selects_strict_for_active_contradiction(self) -> None:
        zero_ai_identity(str(self.base))
        snapshot = self.base / ".zero_os" / "runtime" / "zero_ai_identity_snapshot.json"
        payload = json.loads(snapshot.read_text(encoding="utf-8"))
        payload["classification"] = "unsafe_mutation_engine"
        payload["is_rsi"] = True
        snapshot.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        zero_ai_self_continuity_update(str(self.base))

        status = zero_ai_continuity_policy_auto_status(str(self.base))
        self.assertEqual("strict", status["recommended_policy_level"])

    def test_auto_policy_selects_research_for_high_stability(self) -> None:
        zero_ai_identity(str(self.base))
        state_path = self.base / ".zero_os" / "runtime" / "zero_ai_consciousness_state.json"
        state = {
            "identity": {
                "name": "zero-ai",
                "classification": "computational_consciousness_model",
                "is_rsi": False,
            },
            "self_model": {
                "goals": ["stability", "coherence", "survival"],
                "constraints": ["no_contradiction", "bounded_actions", "auditability"],
                "confidence": 0.95,
                "uncertainty": 0.05,
                "continuity_index": 5,
            },
            "meta_awareness": {
                "introspection_cycles": 5,
                "last_quality_score": 90.0,
                "drift_signals": [],
            },
        }
        state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
        zero_ai_self_continuity_update(str(self.base))

        status = zero_ai_continuity_policy_auto_status(str(self.base))
        self.assertEqual("research", status["recommended_policy_level"])

    def test_auto_policy_apply_switches_to_recommended_level(self) -> None:
        zero_ai_identity(str(self.base))
        state_path = self.base / ".zero_os" / "runtime" / "zero_ai_consciousness_state.json"
        state = {
            "identity": {
                "name": "zero-ai",
                "classification": "computational_consciousness_model",
                "is_rsi": False,
            },
            "self_model": {
                "goals": ["stability", "coherence", "survival"],
                "constraints": ["no_contradiction", "bounded_actions", "auditability"],
                "confidence": 0.65,
                "uncertainty": 0.75,
                "continuity_index": 1,
            },
            "meta_awareness": {
                "introspection_cycles": 1,
                "last_quality_score": 40.0,
                "drift_signals": ["uncertainty_spike"],
            },
        }
        state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
        zero_ai_self_continuity_update(str(self.base))

        applied = zero_ai_continuity_policy_auto_apply(str(self.base))
        self.assertTrue(applied["ok"])
        self.assertTrue(applied["applied"])
        self.assertEqual("strict", applied["active_policy_level"])
        self.assertEqual("strict", applied["recommended_policy_level"])

    def test_continuity_governance_status_defaults(self) -> None:
        zero_ai_identity(str(self.base))
        status = zero_ai_continuity_governance_status(str(self.base))
        self.assertTrue(status["ok"])
        self.assertFalse(status["enabled"])
        self.assertEqual(180, status["interval_seconds"])

    def test_continuity_governance_tick_requires_enable(self) -> None:
        zero_ai_identity(str(self.base))
        tick = zero_ai_continuity_governance_tick(str(self.base))
        self.assertFalse(tick["ok"])
        self.assertFalse(tick["ran"])

    def test_continuity_governance_auto_status_recommends_off_when_stable(self) -> None:
        zero_ai_identity(str(self.base))
        zero_ai_self_continuity_update(str(self.base))
        status = zero_ai_continuity_governance_auto_status(str(self.base))
        self.assertTrue(status["ok"])
        self.assertFalse(status["recommended_enabled"])

    def test_continuity_governance_auto_apply_turns_on_when_risky(self) -> None:
        zero_ai_identity(str(self.base))
        snapshot = self.base / ".zero_os" / "runtime" / "zero_ai_identity_snapshot.json"
        payload = json.loads(snapshot.read_text(encoding="utf-8"))
        payload["classification"] = "unsafe_mutation_engine"
        payload["is_rsi"] = True
        snapshot.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        zero_ai_self_continuity_update(str(self.base))

        applied = zero_ai_continuity_governance_auto_apply(str(self.base))
        self.assertTrue(applied["ok"])
        self.assertTrue(applied["applied"])
        self.assertTrue(applied["governance"]["enabled"])

    def test_continuity_governance_tick_runs_when_enabled(self) -> None:
        zero_ai_identity(str(self.base))
        zero_ai_continuity_governance_set(str(self.base), True, 120)
        tick = zero_ai_continuity_governance_tick(str(self.base))
        self.assertTrue(tick["ok"])
        self.assertTrue(tick["ran"])
        self.assertTrue(tick["result"]["ok"])

    def test_continuity_governance_run_restores_last_safe_if_needed(self) -> None:
        zero_ai_identity(str(self.base))
        zero_ai_self_continuity_update(str(self.base))

        snapshot = self.base / ".zero_os" / "runtime" / "zero_ai_identity_snapshot.json"
        payload = json.loads(snapshot.read_text(encoding="utf-8"))
        payload["classification"] = "unsafe_mutation_engine"
        payload["is_rsi"] = True
        snapshot.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        zero_ai_self_continuity_update(str(self.base))

        run = zero_ai_continuity_governance_run(str(self.base))
        self.assertTrue(run["ok"])
        self.assertTrue(run["restore_used"])
        self.assertTrue(run["continuity_after"]["same_system"])
        self.assertFalse(run["continuity_after"]["has_contradiction"])

    def test_strict_policy_blocks_mild_drift_that_balanced_allows(self) -> None:
        zero_ai_identity(str(self.base))
        proposal = {"state": {"self_model": {"confidence": 1.1}}}

        balanced = zero_ai_continuity_simulate(str(self.base), proposal=proposal)
        self.assertTrue(balanced["safe"])

        zero_ai_continuity_policy_set(str(self.base), "strict")
        strict = zero_ai_continuity_simulate(str(self.base), proposal=proposal)
        self.assertFalse(strict["safe"])

        zero_ai_continuity_policy_set(str(self.base), "research")
        research = zero_ai_continuity_simulate(str(self.base), proposal=proposal)
        self.assertTrue(research["safe"])

    def test_continuity_governor_blocks_unsafe_identity_change(self) -> None:
        zero_ai_identity(str(self.base))
        snapshot = self.base / ".zero_os" / "runtime" / "zero_ai_identity_snapshot.json"
        payload = json.loads(snapshot.read_text(encoding="utf-8"))
        payload["classification"] = "unsafe_mutation_engine"
        payload["is_rsi"] = True
        snapshot.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        check = zero_ai_continuity_governor_check(str(self.base))
        self.assertFalse(check["safe"])
        self.assertGreaterEqual(len(check["blocked_reasons"]), 1)
        applied = zero_ai_continuity_governor_apply(str(self.base))
        self.assertFalse(applied["ok"])
        self.assertTrue(applied["blocked"])

    def test_continuity_simulation_detects_unsafe_future_state(self) -> None:
        zero_ai_identity(str(self.base))
        proposal = {"identity": {"classification": "unsafe_mutation_engine", "is_rsi": True}}
        simulation = zero_ai_continuity_simulate(str(self.base), proposal=proposal)
        self.assertTrue(simulation["simulated"])
        self.assertFalse(simulation["safe"])
        self.assertGreaterEqual(len(simulation["blocked_reasons"]), 1)

    def test_continuity_simulation_apply_commits_safe_change(self) -> None:
        zero_ai_identity(str(self.base))
        proposal = {"state": {"self_model": {"confidence": 0.9, "uncertainty": 0.1}}}
        applied = zero_ai_continuity_simulate_apply(str(self.base), proposal=proposal)
        self.assertTrue(applied["ok"])
        status = zero_ai_self_continuity_status(str(self.base))
        self.assertTrue(status["continuity"]["same_system"])

    def test_patch_file_proposal_can_be_loaded(self) -> None:
        zero_ai_identity(str(self.base))
        proposal_path = self.base / "proposal.json"
        proposal_path.write_text(
            json.dumps({"state": {"self_model": {"confidence": 0.88, "uncertainty": 0.12}}}, indent=2) + "\n",
            encoding="utf-8",
        )
        proposal = json.loads(proposal_path.read_text(encoding="utf-8"))
        simulated = zero_ai_continuity_simulate(str(self.base), proposal=proposal)
        self.assertTrue(simulated["simulated"])
        self.assertTrue(simulated["safe"])

    def test_manual_checkpoint_status_and_create_work(self) -> None:
        zero_ai_identity(str(self.base))
        created = zero_ai_continuity_checkpoint_create(str(self.base), reason="manual_test")
        self.assertTrue(created["ok"])
        status = zero_ai_continuity_checkpoint_status(str(self.base))
        self.assertTrue(status["ok"])
        self.assertGreaterEqual(status["checkpoint_count"], 1)


if __name__ == "__main__":
    unittest.main()
