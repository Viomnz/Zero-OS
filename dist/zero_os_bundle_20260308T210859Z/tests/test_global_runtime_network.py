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


class GlobalRuntimeNetworkTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_grn_")
        self.base = Path(self.tempdir)
        self.highway = Highway(cwd=str(self.base))

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_node_cache_release_security_and_telemetry(self) -> None:
        n = self.highway.dispatch("runtime network node register os=linux device=desktop mode=jit", cwd=str(self.base))
        self.assertTrue(json.loads(n.summary)["ok"])
        d = self.highway.dispatch("runtime network node discover os=linux", cwd=str(self.base))
        self.assertEqual(1, json.loads(d.summary)["total"])

        c = self.highway.dispatch("runtime network cache put app=Demo version=1.0 region=us-west", cwd=str(self.base))
        self.assertTrue(json.loads(c.summary)["ok"])
        cs = self.highway.dispatch("runtime network cache status", cwd=str(self.base))
        self.assertEqual(1, json.loads(cs.summary)["total"])

        rp = self.highway.dispatch("runtime network release propagate version=2.0.0", cwd=str(self.base))
        self.assertTrue(json.loads(rp.summary)["ok"])
        sv = self.highway.dispatch("runtime network security validate signed=true", cwd=str(self.base))
        self.assertTrue(json.loads(sv.summary)["ok"])
        ad = self.highway.dispatch("runtime network adaptive mode device=smartphone", cwd=str(self.base))
        self.assertEqual("optimized-bytecode", json.loads(ad.summary)["execution_mode"])

        st = self.highway.dispatch("runtime network status", cwd=str(self.base))
        self.assertTrue(json.loads(st.summary)["ok"])
        tm = self.highway.dispatch("runtime network telemetry", cwd=str(self.base))
        self.assertTrue(json.loads(tm.summary)["ok"])


if __name__ == "__main__":
    unittest.main()
