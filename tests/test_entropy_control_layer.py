import json
import shutil
import tempfile
import unittest
from pathlib import Path

from ai_from_scratch.entropy_control_layer import control_entropy


class EntropyControlLayerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_entropy_")
        self.base = Path(self.tempdir)
        self.runtime = self.base / ".zero_os" / "runtime"
        self.runtime.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_entropy_low_when_data_clean(self) -> None:
        learning = {"history": [{"prompt": f"p{i}", "outcome_match": True, "learning_score": 0.9} for i in range(8)]}
        trace = {
            "history": [
                {"input": {"prompt": f"p{i}"}, "final_action": {"execute": bool(i % 2)}}
                for i in range(8)
            ]
        }
        knowledge = {"sources": [{"source": "input_text", "type": "prompt"}], "last": {}}
        (self.runtime / "learning_feedback.json").write_text(json.dumps(learning), encoding="utf-8")
        (self.runtime / "decision_trace.json").write_text(json.dumps(trace), encoding="utf-8")
        (self.runtime / "knowledge_model.json").write_text(json.dumps(knowledge), encoding="utf-8")
        out = control_entropy(str(self.base), threshold=0.55)
        self.assertTrue(out["ok"])
        self.assertLess(out["entropy_level"], 0.55)

    def test_entropy_high_triggers_reorganization(self) -> None:
        learning = {"history": [{"prompt": "same", "outcome_match": True, "learning_score": 0.9} for _ in range(30)]}
        trace = {"history": [{"input": {"prompt": "same"}, "final_action": {"execute": True}} for _ in range(30)]}
        knowledge = {
            "sources": [
                {"source": "a", "type": "x"},
                {"source": "b", "type": "x"},
                {"source": "c", "type": "x"},
                {"source": "d", "type": "x"},
                {"source": "d", "type": "x"},
            ],
            "last": {},
        }
        (self.runtime / "learning_feedback.json").write_text(json.dumps(learning), encoding="utf-8")
        (self.runtime / "decision_trace.json").write_text(json.dumps(trace), encoding="utf-8")
        (self.runtime / "knowledge_model.json").write_text(json.dumps(knowledge), encoding="utf-8")
        out = control_entropy(str(self.base), threshold=0.55)
        self.assertGreater(out["entropy_level"], 0.55)
        self.assertTrue(out["actions"]["memory_restructuring"])


if __name__ == "__main__":
    unittest.main()

