import sys
import tempfile
import shutil
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from zero_os.highway import Highway


class CoreRoutingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_os_highway_")
        self.base = Path(self.tempdir)

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_core_status_route(self) -> None:
        highway = Highway(cwd=str(self.base))
        result = highway.dispatch("core status", cwd=str(self.base))
        self.assertEqual("system", result.capability)
        self.assertIn("Unified entity: Zero OS Unified Core", result.summary)

    def test_auto_upgrade(self) -> None:
        highway = Highway(cwd=str(self.base))
        result = highway.dispatch("auto upgrade", cwd=str(self.base))
        self.assertEqual("system", result.capability)
        self.assertIn("Auto-upgrade complete", result.summary)

    def test_plugin_scaffold(self) -> None:
        highway = Highway(cwd=str(self.base))
        result = highway.dispatch("plugin scaffold sample", cwd=str(self.base))
        self.assertEqual("system", result.capability)
        self.assertIn("Plugin scaffold created", result.summary)
        self.assertTrue((self.base / "plugins" / "sample.py").exists())

    def test_law_status_and_export(self) -> None:
        laws = self.base / "laws"
        laws.mkdir(parents=True, exist_ok=True)
        (laws / "recursion_law.txt").write_text("LAW-TEXT", encoding="utf-8")
        highway = Highway(cwd=str(self.base))

        status = highway.dispatch("law status", cwd=str(self.base))
        self.assertEqual("system", status.capability)
        self.assertIn("SHA256:", status.summary)

        exported = highway.dispatch("law export", cwd=str(self.base))
        self.assertEqual("system", exported.capability)
        self.assertEqual("LAW-TEXT", exported.summary)


if __name__ == "__main__":
    unittest.main()
