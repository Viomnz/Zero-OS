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


class RiaRuntimeEconomyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_ria_econ_")
        self.base = Path(self.tempdir)
        self.highway = Highway(cwd=str(self.base))

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_ria_and_economy(self) -> None:
        rs = self.highway.dispatch("ria status", cwd=str(self.base))
        self.assertTrue(json.loads(rs.summary)["ok"])

        program = ["LOAD_RESOURCE", "VERIFY_CAPABILITY", "EXECUTE_COMPUTE", "WRITE_MEMORY", "SYNC_NETWORK"]
        reg = self.highway.dispatch(
            "ria program register app=Calc json=" + json.dumps(program),
            cwd=str(self.base),
        )
        rd = json.loads(reg.summary)
        self.assertTrue(rd["ok"])
        pid = rd["program_id"]

        val = self.highway.dispatch(f"ria program validate id={pid}", cwd=str(self.base))
        self.assertTrue(json.loads(val.summary)["ok"])
        ex = self.highway.dispatch(f'ريا execute id={pid} caps={{"token":true}}'.replace("ريا", "ria"), cwd=str(self.base))
        self.assertTrue(json.loads(ex.summary)["ok"])

        es = self.highway.dispatch("runtime economy status", cwd=str(self.base))
        self.assertTrue(json.loads(es.summary)["ok"])
        ar = self.highway.dispatch("runtime economy actor register role=runtime_node_operator name=nodeop1", cwd=str(self.base))
        aid = json.loads(ar.summary)["actor_id"]
        c = self.highway.dispatch(f"runtime economy contribution actor={aid} kind=compute units=10", cwd=str(self.base))
        self.assertTrue(json.loads(c.summary)["ok"])
        p = self.highway.dispatch(f"runtime economy payout actor={aid} amount=5", cwd=str(self.base))
        self.assertTrue(json.loads(p.summary)["ok"])


if __name__ == "__main__":
    unittest.main()
