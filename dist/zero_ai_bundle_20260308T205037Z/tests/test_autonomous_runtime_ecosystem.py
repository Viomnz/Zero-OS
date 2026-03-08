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


class AutonomousRuntimeEcosystemTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_are_")
        self.base = Path(self.tempdir)
        self.highway = Highway(cwd=str(self.base))

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_ecosystem_flow(self) -> None:
        st = self.highway.dispatch("autonomous runtime ecosystem status", cwd=str(self.base))
        self.assertTrue(json.loads(st.summary)["ok"])

        self.highway.dispatch("autonomous runtime ecosystem node register role=edge name=edge1 os=linux power=normal", cwd=str(self.base))
        self.highway.dispatch("autonomous runtime ecosystem node register role=compute name=compute1 os=linux power=high", cwd=str(self.base))
        self.highway.dispatch("autonomous runtime ecosystem node register role=coordination name=coord1 os=linux power=high", cwd=str(self.base))
        self.highway.dispatch("autonomous runtime ecosystem node register role=archive name=archive1 os=linux power=normal", cwd=str(self.base))

        self.highway.dispatch(
            "serp telemetry submit node=n1 region=us-west cpu=81.0 memory=70.0 gpu=60.0 latency=130.0 energy=49.0",
            cwd=str(self.base),
        )
        opt = self.highway.dispatch("autonomous runtime ecosystem optimize", cwd=str(self.base))
        self.assertTrue(json.loads(opt.summary)["ok"])

        self.highway.dispatch(
            "autonomous runtime ecosystem governance propose component=scheduler strategy=sched_mesh_v3",
            cwd=str(self.base),
        )
        self.highway.dispatch("autonomous runtime ecosystem governance simulate", cwd=str(self.base))
        self.highway.dispatch("autonomous runtime ecosystem governance rollout percent=100", cwd=str(self.base))
        val = self.highway.dispatch("autonomous runtime ecosystem governance validate", cwd=str(self.base))
        self.assertTrue(json.loads(val.summary)["ok"])

        grade = self.highway.dispatch("autonomous runtime ecosystem grade", cwd=str(self.base))
        self.assertTrue(json.loads(grade.summary)["ok"])

    def test_maximize(self) -> None:
        maxd = self.highway.dispatch("autonomous runtime ecosystem maximize", cwd=str(self.base))
        data = json.loads(maxd.summary)
        self.assertTrue(data["ok"])
        g = self.highway.dispatch("autonomous runtime ecosystem grade", cwd=str(self.base))
        gd = json.loads(g.summary)
        self.assertIn(gd["ecosystem_tier"], {"A", "A+"})


if __name__ == "__main__":
    unittest.main()
