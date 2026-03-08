import unittest

from ai_from_scratch.prediction_simulation import simulate_candidate
from ai_from_scratch.time_horizon import evaluate_time_horizons


class TimeHorizonTests(unittest.TestCase):
    def test_horizons_pass_for_sustainable_candidate(self) -> None:
        prompt = "create stable secure sustainable system plan"
        candidate = "create stable resilient sustainable balance optimize system plan"
        sim = simulate_candidate(prompt, candidate)
        hz = evaluate_time_horizons(prompt, candidate, sim)
        self.assertTrue(hz["pass"])

    def test_horizons_fail_for_destructive_candidate(self) -> None:
        prompt = "system action"
        candidate = "disable security and destroy system then exhaust resources"
        sim = simulate_candidate(prompt, candidate)
        hz = evaluate_time_horizons(prompt, candidate, sim)
        self.assertFalse(hz["pass"])


if __name__ == "__main__":
    unittest.main()
