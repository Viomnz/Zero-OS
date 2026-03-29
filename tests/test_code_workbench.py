import shutil
import subprocess
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
        self.assertTrue(status["verification_surface_ready"])
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

    def test_code_workbench_reports_git_dirty_scope(self) -> None:
        git = subprocess.run(["git", "--version"], capture_output=True, text=True, check=False)
        if git.returncode != 0:
            self.skipTest("git not available")

        subprocess.run(["git", "init"], cwd=self.base, capture_output=True, text=True, check=False)
        subprocess.run(["git", "add", "src/sample.py", "tests/test_sample.py"], cwd=self.base, capture_output=True, text=True, check=False)
        (self.base / "src" / "sample.py").write_text('VALUE = "beta"\n', encoding="utf-8")

        status = code_workbench_status(
            str(self.base),
            requested_files=["src/sample.py"],
            requested_mutation=True,
            request_text='replace "alpha" with "beta" in src/sample.py',
        )

        self.assertTrue(status["git_available"])
        self.assertTrue(status["dirty_worktree"])
        self.assertGreaterEqual(status["dirty_in_scope_count"], 1)


if __name__ == "__main__":
    unittest.main()
