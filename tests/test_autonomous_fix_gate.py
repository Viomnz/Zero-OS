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

from zero_os.autonomous_fix_gate import autonomy_evaluate, autonomy_record, autonomy_status
from zero_os.native_store_smart_logic import rollback_decision
from zero_os.runtime_smart_logic import recovery_decision
from zero_os.recovery import zero_ai_backup_create


class AutonomousFixGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_autonomy_")
        self.base = Path(self.tempdir)
        (self.base / ".zero_os").mkdir(parents=True, exist_ok=True)
        (self.base / ".zero_os" / "state.json").write_text("{}", encoding="utf-8")

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_high_risk_without_rollback_holds(self) -> None:
        result = autonomy_evaluate(
            str(self.base),
            action="rollback release",
            blast_radius="system",
            reversible=True,
            evidence_count=8,
            contradictory_signals=0,
            independent_verifiers=3,
            checks={"signed": True, "health_probe": True},
        )
        self.assertTrue(result["ok"])
        self.assertEqual("hold_for_review", result["decision"])
        self.assertEqual("rollback_not_ready", result["decision_reason"])

    def test_high_risk_with_rollback_and_history_can_allow(self) -> None:
        zero_ai_backup_create(str(self.base))
        for _ in range(5):
            autonomy_record(str(self.base), "rollback release", "success", 0.98)
        result = autonomy_evaluate(
            str(self.base),
            action="rollback release",
            blast_radius="service",
            reversible=True,
            evidence_count=12,
            contradictory_signals=0,
            independent_verifiers=4,
            checks={"signed": True, "health_probe": True, "snapshot": True},
        )
        self.assertTrue(result["ok"])
        self.assertEqual("allow", result["decision"])
        self.assertGreaterEqual(result["confidence"]["confidence"], result["threshold"])

    def test_status_tracks_history(self) -> None:
        autonomy_record(str(self.base), "restart service", "success", 0.81)
        status = autonomy_status(str(self.base))
        self.assertTrue(status["ok"])
        self.assertEqual(1, status["history_events"])

    def test_native_store_logic_uses_history_bias(self) -> None:
        plain = rollback_decision(str(self.base), True, "medium")
        for _ in range(4):
            autonomy_record(str(self.base), "native store rollback", "success", 0.92)
        biased = rollback_decision(str(self.base), True, "medium")
        self.assertGreater(biased["confidence"], plain["confidence"])
        self.assertGreaterEqual(biased["autonomy_history"]["count"], 4)

    def test_runtime_logic_uses_history_bias(self) -> None:
        plain = recovery_decision(str(self.base), True, True, "system")
        for _ in range(4):
            autonomy_record(str(self.base), "zero ai recover", "success", 0.95)
        biased = recovery_decision(str(self.base), True, True, "system")
        self.assertGreater(biased["confidence"], plain["confidence"])
        self.assertGreaterEqual(biased["autonomy_history"]["count"], 4)

    def test_history_quality_penalizes_slow_rollback_heavy_outcomes(self) -> None:
        for _ in range(4):
            autonomy_record(
                str(self.base),
                "zero ai recover",
                "success",
                0.95,
                rollback_used=True,
                recovery_seconds=500,
                blast_radius="system",
                verification_passed=True,
            )
        biased = recovery_decision(str(self.base), True, True, "system")
        self.assertLess(biased["autonomy_history"]["quality_score"], 1.0)
        self.assertIn("quality_score", biased["autonomy_history"])

    def test_health_delta_drives_quality_when_snapshots_present(self) -> None:
        rec = autonomy_record(
            str(self.base),
            "self repair run",
            "success",
            0.9,
            health_before={"health_score": 20, "signals": {}},
            health_after={"health_score": 80, "signals": {}},
            verification_passed=True,
        )
        self.assertGreater(rec["event"]["quality"], 0.5)

    def test_planner_confidence_can_hold_medium_risk_action(self) -> None:
        result = autonomy_evaluate(
            str(self.base),
            action="browser action click",
            blast_radius="service",
            reversible=True,
            evidence_count=12,
            contradictory_signals=0,
            independent_verifiers=4,
            checks={"browser_ready": True, "verification_ready": True, "rollback_ready": True},
            planner_confidence=0.41,
            planner_risk_level="medium",
            planner_ambiguity_count=1,
        )

        self.assertTrue(result["ok"])
        self.assertEqual("hold_for_review", result["decision"])
        self.assertEqual("planner_confidence_below_mutation_threshold", result["decision_reason"])
        self.assertEqual(0.41, result["planner"]["confidence"])


if __name__ == "__main__":
    unittest.main()
