import shutil
import tempfile
import unittest
from pathlib import Path

from ai_from_scratch.traceability_layer import audit_trace, log_decision_trace, log_trace_event


class TraceabilityLayerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_trace_")
        self.base = Path(self.tempdir)

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_log_decision_trace_persists_history(self) -> None:
        first = log_decision_trace(str(self.base), {"input": {"prompt": "status"}, "final_action": {"execute": True}})
        second = log_decision_trace(str(self.base), {"input": {"prompt": "scan"}, "final_action": {"execute": False}})
        self.assertTrue(first["ok"])
        self.assertTrue(second["ok"])
        path = self.base / ".zero_os" / "runtime" / "decision_trace.json"
        self.assertTrue(path.exists())
        audit = audit_trace(str(self.base), limit=10)
        self.assertTrue(audit["ok"])
        self.assertGreaterEqual(audit["returned"], 2)
        self.assertEqual(2, audit["events"][-1].get("schema_version"))

    def test_log_trace_event_and_filter(self) -> None:
        log_trace_event(str(self.base), "feedback", {"x": 1})
        log_trace_event(str(self.base), "outcome", {"x": 2})
        only_feedback = audit_trace(str(self.base), limit=10, event_type="feedback")
        self.assertTrue(only_feedback["ok"])
        self.assertEqual(1, only_feedback["returned"])
        self.assertEqual("feedback", only_feedback["events"][0]["event_type"])


if __name__ == "__main__":
    unittest.main()
