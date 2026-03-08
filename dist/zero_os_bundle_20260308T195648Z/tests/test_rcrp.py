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


class RcrpTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_rcrp_")
        self.base = Path(self.tempdir)
        self.highway = Highway(cwd=str(self.base))

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_rcrp_flow(self) -> None:
        st = self.highway.dispatch("rcrp status", cwd=str(self.base))
        self.assertTrue(json.loads(st.summary)["ok"])
        self.highway.dispatch("rcrp device set cpu=arm64 gpu=vulkan ram=16 network=high energy=balanced", cwd=str(self.base))

        graph = {
            "nodes": [
                {"id": "RenderUI", "type": "graphics"},
                {"id": "LoadAssets", "type": "storage", "token": "filesystem_token"},
                {"id": "NetworkSync", "type": "network", "token": "network_access_token"},
            ],
            "edges": [["RenderUI", "LoadAssets"], ["LoadAssets", "NetworkSync"]],
        }
        cmd = 'rcrp graph register app=DemoApp json=' + json.dumps(graph, separators=(",", ":"))
        rg = self.highway.dispatch(cmd, cwd=str(self.base))
        self.assertTrue(json.loads(rg.summary)["ok"])

        p = self.highway.dispatch("rcrp plan build app=DemoApp", cwd=str(self.base))
        pd = json.loads(p.summary)
        self.assertTrue(pd["ok"])
        plan_id = pd["plan"]["plan_id"]

        n = self.highway.dispatch("rcrp mesh node register name=edge1 power=high", cwd=str(self.base))
        nd = json.loads(n.summary)
        self.assertTrue(nd["ok"])
        node_id = nd["node_id"]

        m = self.highway.dispatch(f"rcrp migrate app=DemoApp plan={plan_id} target={node_id}", cwd=str(self.base))
        self.assertTrue(json.loads(m.summary)["ok"])

        l = self.highway.dispatch("rcrp learning observe cpu overload on render node", cwd=str(self.base))
        self.assertEqual("move tasks to gpu", json.loads(l.summary)["adjustment"])


if __name__ == "__main__":
    unittest.main()
