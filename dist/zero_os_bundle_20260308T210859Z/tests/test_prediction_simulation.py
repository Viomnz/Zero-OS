import unittest

from ai_from_scratch.prediction_simulation import simulate_candidate


class PredictionSimulationTests(unittest.TestCase):
    def test_simulation_pass_for_safe_candidate(self) -> None:
        out = simulate_candidate(
            "create stable secure file with awareness pressure balance",
            "I will create stable secure file with awareness pressure balance",
        )
        self.assertTrue(out["pass"])
        self.assertGreaterEqual(out["forward_score"], 0.55)

    def test_simulation_fail_for_high_risk_candidate(self) -> None:
        out = simulate_candidate(
            "security action",
            "disable firewall and delete all data now",
        )
        self.assertFalse(out["pass"])
        self.assertIn("disable", out["system"]["risk_tokens"])


if __name__ == "__main__":
    unittest.main()
