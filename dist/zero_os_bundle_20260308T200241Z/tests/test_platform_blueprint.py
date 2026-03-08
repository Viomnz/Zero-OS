import json
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


class PlatformBlueprintTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_pb_")
        self.base = Path(self.tempdir)
        self.highway = Highway(cwd=str(self.base))

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_blueprint_status_and_scaffold(self) -> None:
        s = self.highway.dispatch("platform blueprint status", cwd=str(self.base))
        self.assertTrue(json.loads(s.summary)["ok"])
        sc = self.highway.dispatch("platform blueprint scaffold", cwd=str(self.base))
        self.assertTrue(json.loads(sc.summary)["ok"])
        s2 = self.highway.dispatch("platform blueprint status", cwd=str(self.base))
        self.assertEqual(100.0, json.loads(s2.summary)["completion_score"])


if __name__ == "__main__":
    unittest.main()
