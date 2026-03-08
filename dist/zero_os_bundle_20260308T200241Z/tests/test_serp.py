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


class SerpTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_serp_")
        self.base = Path(self.tempdir)
        self.highway = Highway(cwd=str(self.base))

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_serp_flow(self) -> None:
        st = self.highway.dispatch("serp status", cwd=str(self.base))
        self.assertTrue(json.loads(st.summary)["ok"])

        self.highway.dispatch(
            "serp telemetry submit node=n1 region=us-west cpu=82.0 memory=71.0 gpu=34.0 latency=120.0 energy=52.0",
            cwd=str(self.base),
        )
        an = self.highway.dispatch("serp analyze", cwd=str(self.base))
        self.assertTrue(json.loads(an.summary)["ok"])

        m = self.highway.dispatch("serp mutation propose component=scheduler strategy=sched_v2 signer=serp-ca", cwd=str(self.base))
        md = json.loads(m.summary)
        self.assertTrue(md["ok"])
        mid = md["mutation"]["id"]

        d = self.highway.dispatch(f"serp deploy staged mutation={mid} percent=100", cwd=str(self.base))
        self.assertTrue(json.loads(d.summary)["ok"])
        rb = self.highway.dispatch("serp rollback", cwd=str(self.base))
        self.assertTrue(json.loads(rb.summary)["ok"])

        ex = self.highway.dispatch('serp state export app=Game json={"mem":"snapshot","cursor":2}', cwd=str(self.base))
        sid = json.loads(ex.summary)["state_id"]
        im = self.highway.dispatch(f"serp state import id={sid} target=nodeB", cwd=str(self.base))
        self.assertTrue(json.loads(im.summary)["ok"])


if __name__ == "__main__":
    unittest.main()
