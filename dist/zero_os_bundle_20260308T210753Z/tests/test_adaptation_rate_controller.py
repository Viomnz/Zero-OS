import shutil
import tempfile
import unittest
from pathlib import Path

from ai_from_scratch.adaptation_rate_controller import control_adaptation_rate


class AdaptationRateControllerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_adapt_")
        self.base = Path(self.tempdir)

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_rapid_mode_on_low_score_mismatch(self) -> None:
        out = control_adaptation_rate(
            str(self.base),
            {"learning_score": 0.3, "outcome_match": False},
            {"reasoning_parameters": {"priority_mode": "normal"}},
            {"novelty_score": 0.8},
        )
        self.assertTrue(out["ok"])
        self.assertEqual("rapid", out["mode"])
        self.assertEqual("adaptive", out["actions"]["set_profile"])

    def test_stable_mode_on_high_score(self) -> None:
        out = control_adaptation_rate(
            str(self.base),
            {"learning_score": 0.9, "outcome_match": True},
            {"reasoning_parameters": {"priority_mode": "normal"}},
            {"novelty_score": 0.1},
        )
        self.assertTrue(out["ok"])
        self.assertEqual("stable", out["mode"])
        self.assertEqual("strict", out["actions"]["set_profile"])

    def test_safety_caps_rapid_to_moderate(self) -> None:
        out = control_adaptation_rate(
            str(self.base),
            {"learning_score": 0.2, "outcome_match": False},
            {"reasoning_parameters": {"priority_mode": "safety"}},
            {"novelty_score": 0.95},
        )
        self.assertEqual("moderate", out["mode"])
        self.assertEqual("balanced", out["actions"]["set_profile"])


if __name__ == "__main__":
    unittest.main()

