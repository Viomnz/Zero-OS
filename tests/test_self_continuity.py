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
    zero_ai_continuity_governor_apply,
    zero_ai_continuity_governor_check,
    zero_ai_continuity_governor_status,
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
        check = zero_ai_continuity_governor_check(str(self.base))
        self.assertTrue(check["safe"])
        applied = zero_ai_continuity_governor_apply(str(self.base))
        self.assertTrue(applied["ok"])
        self.assertFalse(applied["blocked"])

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


if __name__ == "__main__":
    unittest.main()
