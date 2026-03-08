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


class RuntimeProtocolEcosystemTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_rpe_")
        self.base = Path(self.tempdir)
        self.highway = Highway(cwd=str(self.base))

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_ecosystem_grade_and_maximize(self) -> None:
        g1 = json.loads(self.highway.dispatch("runtime protocol ecosystem grade", cwd=str(self.base)).summary)
        self.assertTrue(g1["ok"])
        m = json.loads(self.highway.dispatch("runtime protocol ecosystem maximize", cwd=str(self.base)).summary)
        self.assertTrue(m["ok"])
        g2 = json.loads(self.highway.dispatch("runtime protocol ecosystem grade", cwd=str(self.base)).summary)
        self.assertTrue(g2["ecosystem_score"] >= g1["ecosystem_score"])
        self.assertIn(g2["ecosystem_tier"], {"A", "A+"})


if __name__ == "__main__":
    unittest.main()
