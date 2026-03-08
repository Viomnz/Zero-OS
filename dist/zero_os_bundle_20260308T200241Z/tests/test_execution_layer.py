import shutil
import tempfile
import unittest
from pathlib import Path

from ai_from_scratch.execution_layer import execute_decision


class ExecutionLayerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_exec_")
        self.base = Path(self.tempdir)

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_execute_when_prechecks_pass(self) -> None:
        out = execute_decision(
            str(self.base),
            "done",
            "human",
            {"reasoning_parameters": {"priority_mode": "normal"}},
            {"decision": "approve"},
            {"stable": True},
        )
        self.assertTrue(out["ok"])
        self.assertTrue(out["executed"])
        self.assertTrue(out["dispatch"]["allowed"])

    def test_block_when_resource_not_approved(self) -> None:
        out = execute_decision(
            str(self.base),
            "done",
            "human",
            {"reasoning_parameters": {"priority_mode": "normal"}},
            {"decision": "reject"},
            {"stable": True},
        )
        self.assertFalse(out["executed"])
        self.assertEqual("precheck_failed", out["reason"])


if __name__ == "__main__":
    unittest.main()

