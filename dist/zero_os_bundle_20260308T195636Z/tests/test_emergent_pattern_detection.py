import json
import shutil
import tempfile
import unittest
from pathlib import Path

from ai_from_scratch.emergent_pattern_detection import detect_emergent_patterns


class EmergentPatternDetectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_emergent_")
        self.base = Path(self.tempdir)
        self.runtime = self.base / ".zero_os" / "runtime"
        self.runtime.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_detects_behavioral_repetition(self) -> None:
        learning = {"history": [{"prompt": "status", "outcome_match": True} for _ in range(4)]}
        (self.runtime / "learning_feedback.json").write_text(json.dumps(learning), encoding="utf-8")
        out = detect_emergent_patterns(
            str(self.base),
            "status",
            {"reasoning_parameters": {"priority_mode": "normal"}},
            {"unified_model": {"source_count": 1}},
        )
        self.assertTrue(out["ok"])
        self.assertIn("behavioral_repetition", out["patterns"])

    def test_detects_feedback_drift(self) -> None:
        learning = {"history": [{"prompt": "x", "outcome_match": False} for _ in range(8)]}
        trace = {"history": [{"final_action": {"execute": False}} for _ in range(20)]}
        (self.runtime / "learning_feedback.json").write_text(json.dumps(learning), encoding="utf-8")
        (self.runtime / "decision_trace.json").write_text(json.dumps(trace), encoding="utf-8")
        out = detect_emergent_patterns(
            str(self.base),
            "x",
            {"reasoning_parameters": {"priority_mode": "normal"}},
            {"unified_model": {"source_count": 2}},
        )
        self.assertIn("feedback_drift", out["patterns"])
        self.assertEqual("adaptive", out["actions"]["set_profile"])


if __name__ == "__main__":
    unittest.main()

