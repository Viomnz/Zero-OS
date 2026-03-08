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


class HardwareRuntimeFabricTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_hrf_")
        self.base = Path(self.tempdir)
        self.highway = Highway(cwd=str(self.base))

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_hardware_evolution_memory_fabric(self) -> None:
        s = self.highway.dispatch("hardware runtime status", cwd=str(self.base))
        self.assertTrue(json.loads(s.summary)["ok"])
        mx = self.highway.dispatch("hardware runtime maximize", cwd=str(self.base))
        self.assertTrue(json.loads(mx.summary)["ok"])

        # Seed SERP telemetry so evolve has signal
        self.highway.dispatch(
            "serp telemetry submit node=n1 region=us-west cpu=80.0 memory=75.0 gpu=85.0 latency=140.0 energy=50.0",
            cwd=str(self.base),
        )
        ev = self.highway.dispatch("runtime evolve app DemoApp", cwd=str(self.base))
        self.assertTrue(json.loads(ev.summary)["ok"])

        ml = self.highway.dispatch("runtime memory learn app=DemoApp key=render value=gpu_batch", cwd=str(self.base))
        self.assertTrue(json.loads(ml.summary)["ok"])
        mg = self.highway.dispatch("runtime memory get app=DemoApp", cwd=str(self.base))
        self.assertIn("render", json.loads(mg.summary)["patterns"])

        n = self.highway.dispatch("runtime fabric node register name=edge-a power=high", cwd=str(self.base))
        self.assertTrue(json.loads(n.summary)["ok"])
        d = self.highway.dispatch("runtime fabric dispatch app=DemoApp task=physics nodes=1", cwd=str(self.base))
        self.assertTrue(json.loads(d.summary)["ok"])
        fs = self.highway.dispatch("runtime fabric status", cwd=str(self.base))
        self.assertTrue(json.loads(fs.summary)["ok"])


if __name__ == "__main__":
    unittest.main()
