import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from zero_os.highway import Highway


class PluginTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_os_plugin_")
        self.base = Path(self.tempdir)
        plugins = self.base / "plugins"
        plugins.mkdir(parents=True, exist_ok=True)
        plugin_code = '''
from zero_os.types import Result

class EchoCap:
    name = "echo"
    def can_handle(self, task):
        return task.text.lower().startswith("echo ")
    def run(self, task):
        return Result(self.name, task.text[5:])

def get_capability():
    return EchoCap()
'''
        (plugins / "echo_plugin.py").write_text(plugin_code, encoding="utf-8")

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_plugin_loaded_and_routed(self) -> None:
        highway = Highway(cwd=str(self.base))
        result = highway.dispatch("echo hello", cwd=str(self.base))
        self.assertEqual("echo", result.capability)
        self.assertEqual("hello", result.summary)


if __name__ == "__main__":
    unittest.main()
