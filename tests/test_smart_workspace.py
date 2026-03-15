import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from zero_os.smart_workspace import workspace_refresh, workspace_status


class SmartWorkspaceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_smart_workspace_")
        self.base = Path(self.tempdir)
        (self.base / "src").mkdir(parents=True, exist_ok=True)
        (self.base / "tests").mkdir(parents=True, exist_ok=True)
        (self.base / "README.md").write_text("# Demo\n", encoding="utf-8")
        (self.base / "src" / "app.py").write_text("def main():\n    return 'ok'\n", encoding="utf-8")
        (self.base / "tests" / "test_app.py").write_text("def test_main():\n    assert True\n", encoding="utf-8")

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_workspace_status_surfaces_missing_index_baseline(self) -> None:
        status = workspace_status(str(self.base))
        self.assertTrue(status["ok"])
        self.assertFalse(status["summary"]["indexed"])
        self.assertTrue(any("workspace refresh" in step.lower() for step in status["highest_value_steps"]))

    def test_workspace_refresh_builds_indexed_map(self) -> None:
        status = workspace_refresh(str(self.base))
        self.assertTrue(status["ok"])
        self.assertTrue(status["summary"]["indexed"])
        self.assertTrue(status["summary"]["search_ready"])
        self.assertGreaterEqual(status["summary"]["file_count"], 2)
        self.assertGreaterEqual(status["summary"]["symbol_file_count"], 1)


if __name__ == "__main__":
    unittest.main()
