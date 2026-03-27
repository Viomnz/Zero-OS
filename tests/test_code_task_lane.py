import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from zero_os.code_task_lane import run_code_task


class CodeTaskLaneTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_code_task_lane_")
        self.base = Path(self.tempdir)
        (self.base / "src").mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_run_code_task_applies_replace_and_keeps_successful_candidate(self) -> None:
        target = self.base / "src" / "sample.py"
        target.write_text('VALUE = "alpha"\n', encoding="utf-8")

        result = run_code_task(
            str(self.base),
            {
                "request": 'replace "alpha" with "beta" in src/sample.py',
                "files": ["src/sample.py"],
                "instruction": {"ok": True, "operation": "replace", "old": "alpha", "new": "beta"},
            },
        )

        self.assertTrue(result["ok"])
        self.assertIn("src/sample.py", result["changed_files"])
        self.assertEqual('VALUE = "beta"\n', target.read_text(encoding="utf-8"))
        self.assertTrue(result["verification"]["compile"]["ok"])

    def test_run_code_task_reverts_failed_candidate_after_compile_error(self) -> None:
        target = self.base / "src" / "sample.py"
        original = "VALUE = 1\n"
        target.write_text(original, encoding="utf-8")

        result = run_code_task(
            str(self.base),
            {
                "request": 'replace "1" with ")" in src/sample.py',
                "files": ["src/sample.py"],
                "instruction": {"ok": True, "operation": "replace", "old": "1", "new": ")"},
            },
        )

        self.assertFalse(result["ok"])
        self.assertEqual("verification_failed", result["reason"])
        self.assertEqual(original, target.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
