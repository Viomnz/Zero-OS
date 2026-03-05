import shutil
import tempfile
import unittest
from pathlib import Path

from ai_from_scratch.traceability_layer import log_decision_trace


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


if __name__ == "__main__":
    unittest.main()

