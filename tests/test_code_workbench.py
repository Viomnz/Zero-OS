import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from zero_os.code_workbench import code_workbench_status


class CodeWorkbenchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_code_workbench_")
        self.base = Path(self.tempdir)
        (self.base / "src").mkdir(parents=True, exist_ok=True)
        (self.base / "tests").mkdir(parents=True, exist_ok=True)
        (self.base / "src" / "sample.py").write_text('VALUE = "alpha"\n', encoding="utf-8")
        (self.base / "tests" / "test_sample.py").write_text("def test_placeholder():\n    assert True\n", encoding="utf-8")

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_code_workbench_reports_scope_and_verification_ready(self) -> None:
        status = code_workbench_status(
            str(self.base),
            requested_files=["src/sample.py"],
            requested_mutation=True,
            request_text='replace "alpha" with "beta" in src/sample.py',
        )

        self.assertTrue(status["workspace_ready"])
        self.assertTrue(status["scope_ready"])
        self.assertTrue(status["verification_ready"])
        self.assertEqual(1, status["compile_target_count"])
        self.assertIn("tests/test_sample.py", status["focused_test_targets"])

    def test_code_workbench_marks_out_of_scope_targets(self) -> None:
        status = code_workbench_status(
            str(self.base),
            requested_files=["README.md"],
            requested_mutation=True,
            request_text='replace "alpha" with "beta" in README.md',
        )

        self.assertFalse(status["scope_ready"])
        self.assertEqual(1, status["out_of_scope_count"])
        self.assertIn("README.md", status["out_of_scope_files"])


if __name__ == "__main__":
    unittest.main()

