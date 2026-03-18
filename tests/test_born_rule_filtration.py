import unittest

from ai_from_scratch.born_rule_filtration import (
    amplitude_probability,
    derive_born_rule_from_filtration,
    evaluate_candidate_exponent,
)


class BornRuleFiltrationTests(unittest.TestCase):
    def test_amplitude_probability_matches_born_square(self) -> None:
        probability = amplitude_probability(0.3 + 0.4j, 2.0)
        self.assertAlmostEqual(0.25, probability, places=9)

    def test_non_born_power_law_fails_coarse_grain_additivity(self) -> None:
        report = evaluate_candidate_exponent(1.0)
        self.assertGreater(report.additive_error, 0.01)
        self.assertAlmostEqual(0.0, report.composition_error, places=9)

    def test_filtration_derivation_selects_exponent_two(self) -> None:
        report = derive_born_rule_from_filtration()
        self.assertEqual(2.0, report["winner"]["amplitude_exponent"])
        self.assertEqual([2.0], report["passing_amplitude_exponents"])
        self.assertTrue(report["born_rule_unique"])
        self.assertEqual("P(a) = |a|^2", report["derived_probability_law"])


if __name__ == "__main__":
    unittest.main()
