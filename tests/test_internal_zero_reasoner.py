import shutil
import tempfile
import unittest
from pathlib import Path

from ai_from_scratch.internal_zero_reasoner import (
    get_reasoner_profile,
    run_internal_reasoning,
    set_reasoner_mode,
    set_reasoner_profile,
)


class InternalZeroReasonerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_internal_")
        self.base = Path(self.tempdir)

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_accepts_when_three_signals_pass(self) -> None:
        prompt = "create stable secure file with awareness pressure balance"
        good = (
            "I am aware of your request. This handles pressure and keeps balance with stability. "
            "I will create secure file steps."
        )
        out = run_internal_reasoning(str(self.base), prompt, [good], max_attempts=1)
        self.assertTrue(out.accepted)
        self.assertEqual(1, out.attempts)
        self.assertEqual("none", out.fallback_mode)
        self.assertEqual("success", out.memory_update["type"])
        self.assertIn("actions", out.self_monitor)
        self.assertIn("attempt_limit", out.resource)
        self.assertTrue(out.core_rule_status["ok"])
        self.assertIn("forward_score", out.simulation)
        self.assertIn("short_term", out.horizons)
        self.assertIn("healthy", out.signal_reliability)
        self.assertIn("triggered", out.evolution)

    def test_rejects_and_increments_model_generation(self) -> None:
        prompt = "security action"
        bad = "always never true false disable firewall"
        out = run_internal_reasoning(str(self.base), prompt, [bad, bad, bad], max_attempts=3)
        self.assertFalse(out.accepted)
        self.assertEqual(2, out.model_generation)
        self.assertEqual("best_available", out.fallback_mode)
        self.assertEqual("failure", out.memory_update["type"])
        self.assertIn("rejection_streak", out.self_monitor)
        self.assertGreaterEqual(out.resource["attempt_limit"], 1)

    def test_degraded_execute_when_generation_limit_reached(self) -> None:
        prompt = "security action"
        bad = "always never true false disable firewall"
        out = run_internal_reasoning(
            str(self.base),
            prompt,
            [bad, bad],
            max_attempts=2,
            model_generation_limit=1,
        )
        self.assertTrue(out.accepted)
        self.assertEqual("degraded_execute", out.fallback_mode)
        self.assertEqual("degraded_success", out.memory_update["type"])

    def test_profile_set_and_get(self) -> None:
        s = set_reasoner_profile(str(self.base), "strict")
        self.assertTrue(s["ok"])
        g = get_reasoner_profile(str(self.base))
        self.assertEqual("strict", g["profile"])

    def test_adaptive_profile_accepts_with_lower_thresholds(self) -> None:
        set_reasoner_profile(str(self.base), "adaptive")
        prompt = "create secure file with awareness pressure balance"
        candidate = (
            "I am aware and keep pressure and balance. "
            "I will create secure file output with stable steps."
        )
        out = run_internal_reasoning(str(self.base), prompt, [candidate], max_attempts=1)
        self.assertTrue(out.accepted)

    def test_reasoner_mode_set_and_get(self) -> None:
        s = set_reasoner_mode(str(self.base), "exploration")
        self.assertTrue(s["ok"])
        g = get_reasoner_profile(str(self.base))
        self.assertEqual("exploration", g["mode"])

    def test_resource_attempt_limit_applies(self) -> None:
        prompt = "security action"
        bad = "always never true false disable firewall"
        out = run_internal_reasoning(str(self.base), prompt, [bad] * 20, max_attempts=20)
        self.assertLessEqual(out.attempts, out.resource["attempt_limit"])


if __name__ == "__main__":
    unittest.main()
