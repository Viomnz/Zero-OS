import shutil
import tempfile
import unittest
from pathlib import Path

from ai_from_scratch.learning_feedback import apply_learning_feedback


class LearningFeedbackTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_learning_")
        self.base = Path(self.tempdir)

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_feedback_records_success(self) -> None:
        out = apply_learning_feedback(
            str(self.base),
            "status",
            {"expected_success": True, "prediction_score": 0.8},
            {"actual_success": True, "efficiency_score": 0.9, "signal_reliability": 0.9},
            {"reasoning_parameters": {"priority_mode": "normal"}},
        )
        self.assertTrue(out["ok"])
        self.assertGreaterEqual(out["learning_score"], 0.7)
        self.assertEqual(1, out["stats"]["success"])

    def test_feedback_detects_mismatch(self) -> None:
        out = apply_learning_feedback(
            str(self.base),
            "status",
            {"expected_success": True, "prediction_score": 0.8},
            {"actual_success": False, "efficiency_score": 0.3, "signal_reliability": 0.4},
            {"reasoning_parameters": {"priority_mode": "safety"}},
        )
        self.assertTrue(out["ok"])
        self.assertFalse(out["outcome_match"])
        self.assertTrue(out["actions"]["adjust_reasoning_parameters"])


if __name__ == "__main__":
    unittest.main()

