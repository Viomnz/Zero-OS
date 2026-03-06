import json
import shutil
import tempfile
import unittest
from pathlib import Path

from ai_from_scratch.compression_simplification_layer import run_compression


class CompressionSimplificationLayerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_compress_")
        self.base = Path(self.tempdir)
        self.runtime = self.base / ".zero_os" / "runtime"
        self.runtime.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_dedupes_redundant_history(self) -> None:
        learning = {
            "history": [
                {"prompt": "status", "outcome_match": True, "learning_score": 0.91},
                {"prompt": "status", "outcome_match": True, "learning_score": 0.912},
                {"prompt": "scan", "outcome_match": False, "learning_score": 0.4},
            ]
        }
        trace = {
            "history": [
                {"input": {"prompt": "status"}, "consensus": {"accepted": True}, "final_action": {"execute": True}},
                {"input": {"prompt": "status"}, "consensus": {"accepted": True}, "final_action": {"execute": True}},
                {"input": {"prompt": "scan"}, "consensus": {"accepted": False}, "final_action": {"execute": False}},
            ]
        }
        (self.runtime / "learning_feedback.json").write_text(json.dumps(learning), encoding="utf-8")
        (self.runtime / "decision_trace.json").write_text(json.dumps(trace), encoding="utf-8")

        out = run_compression(str(self.base), threshold_entries=300)
        self.assertTrue(out["ok"])
        self.assertGreaterEqual(out["removed"]["learning_feedback"], 1)
        self.assertGreaterEqual(out["removed"]["decision_trace"], 1)

    def test_applies_threshold_trim(self) -> None:
        learning = {"history": [{"prompt": f"p{i}", "outcome_match": True, "learning_score": 0.9} for i in range(10)]}
        trace = {
            "history": [
                {"input": {"prompt": f"p{i}"}, "consensus": {"accepted": True}, "final_action": {"execute": True}}
                for i in range(10)
            ]
        }
        (self.runtime / "learning_feedback.json").write_text(json.dumps(learning), encoding="utf-8")
        (self.runtime / "decision_trace.json").write_text(json.dumps(trace), encoding="utf-8")

        out = run_compression(str(self.base), threshold_entries=5)
        self.assertGreaterEqual(out["after"]["learning_feedback"], 5)
        self.assertGreaterEqual(out["after"]["decision_trace"], 5)
        self.assertIn("integrity", out)
        self.assertFalse(out["rolled_back"])

    def test_preserves_critical_negative_learning(self) -> None:
        learning = {
            "history": [
                {"prompt": f"p{i}", "outcome_match": True, "learning_score": 0.8, "signal_type": "positive"}
                for i in range(12)
            ]
            + [
                {"prompt": "critical", "outcome_match": False, "learning_score": 0.2, "signal_type": "negative"}
            ]
        }
        trace = {"history": []}
        (self.runtime / "learning_feedback.json").write_text(json.dumps(learning), encoding="utf-8")
        (self.runtime / "decision_trace.json").write_text(json.dumps(trace), encoding="utf-8")

        out = run_compression(str(self.base), threshold_entries=5)
        self.assertTrue(out["ok"])
        saved = json.loads((self.runtime / "learning_feedback.json").read_text(encoding="utf-8"))
        prompts = [x.get("prompt") for x in saved.get("history", [])]
        self.assertIn("critical", prompts)


if __name__ == "__main__":
    unittest.main()
