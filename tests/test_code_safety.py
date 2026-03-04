import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from zero_os.capabilities.code import CodeCapability
from zero_os.types import Task


class CodeSafetyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_os_test_")
        self.base = Path(self.tempdir)
        self.cap = CodeCapability()

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_blocks_path_escape(self) -> None:
        task = Task(text="create file ../hack.txt with nope", cwd=str(self.base))
        result = self.cap.run(task)
        self.assertIn("Blocked: path escapes workspace", result.summary)

    def test_blocks_protected_delete(self) -> None:
        protected = self.base / ".zero_os"
        protected.mkdir(parents=True, exist_ok=True)
        task = Task(text="delete .zero_os", cwd=str(self.base))
        result = self.cap.run(task)
        self.assertIn("Blocked: protected path", result.summary)

    def test_chained_actions_work(self) -> None:
        task = Task(
            text="new file notes/a.txt with hi then add to notes/a.txt: there then show notes/a.txt",
            cwd=str(self.base),
        )
        result = self.cap.run(task)
        self.assertIn("1. Created file:", result.summary)
        self.assertIn("2. Appended to file:", result.summary)
        self.assertIn("3.", result.summary)


if __name__ == "__main__":
    unittest.main()
