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


class StoreProductionOpsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_store_prod_")
        self.base = Path(self.tempdir)
        self.highway = Highway(cwd=str(self.base))
        pkg = self.base / "pkg"
        (pkg / "builds").mkdir(parents=True, exist_ok=True)
        (pkg / "metadata").mkdir(parents=True, exist_ok=True)
        (pkg / "signature").mkdir(parents=True, exist_ok=True)
        (pkg / "builds" / "linux_x64.bin").write_bytes(b"bin")
        (pkg / "signature" / "developer.sig").write_text("sig", encoding="utf-8")
        manifest = {"name": "ProdApp", "version": "1.0", "targets": {"linux": "builds/linux_x64.bin"}}
        (pkg / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        self.highway.dispatch("store publish pkg", cwd=str(self.base))

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_full_production_flow(self) -> None:
        a = self.highway.dispatch("store account create email=test@example.com tier=pro", cwd=str(self.base))
        ad = json.loads(a.summary)
        self.assertTrue(ad["ok"])
        uid = ad["user_id"]

        b = self.highway.dispatch(f"store billing charge user={uid} amount=9.99 currency=USD", cwd=str(self.base))
        self.assertTrue(json.loads(b.summary)["ok"])
        l = self.highway.dispatch(f"store license grant user={uid} app=ProdApp", cwd=str(self.base))
        self.assertTrue(json.loads(l.summary)["ok"])

        i = self.highway.dispatch(f"store install user={uid} app=ProdApp os=linux", cwd=str(self.base))
        iid = json.loads(i.summary)["install"]["install_id"]
        u = self.highway.dispatch(f"store upgrade id={iid} version=1.1", cwd=str(self.base))
        self.assertTrue(json.loads(u.summary)["ok"])
        un = self.highway.dispatch(f"store uninstall id={iid}", cwd=str(self.base))
        self.assertTrue(json.loads(un.summary)["ok"])

        se = self.highway.dispatch("store security enforce app=ProdApp", cwd=str(self.base))
        self.assertTrue(json.loads(se.summary)["ok"])
        rp1 = self.highway.dispatch("store replicate app=ProdApp version=1.0", cwd=str(self.base))
        self.assertTrue(json.loads(rp1.summary)["ok"])
        self.highway.dispatch("store replicate app=ProdApp version=1.0", cwd=str(self.base))
        rb = self.highway.dispatch("store rollback app=ProdApp version=1.0", cwd=str(self.base))
        self.assertTrue(json.loads(rb.summary)["ok"])

        rv = self.highway.dispatch(f"store review add app=ProdApp user={uid} rating=5 text=great", cwd=str(self.base))
        self.assertTrue(json.loads(rv.summary)["ok"])
        sr = self.highway.dispatch("store search Prod", cwd=str(self.base))
        self.assertTrue(json.loads(sr.summary)["ok"])
        an = self.highway.dispatch("store analytics status", cwd=str(self.base))
        self.assertTrue(json.loads(an.summary)["ok"])

        pol = self.highway.dispatch("store policy ios external off", cwd=str(self.base))
        self.assertTrue(json.loads(pol.summary)["ok"])
        comp = self.highway.dispatch("store compliance status", cwd=str(self.base))
        self.assertTrue(json.loads(comp.summary)["ok"])

        slo = self.highway.dispatch("store slo set availability=99.95 p95=90", cwd=str(self.base))
        self.assertTrue(json.loads(slo.summary)["ok"])
        ab = self.highway.dispatch("store abuse block ip 1.2.3.4", cwd=str(self.base))
        self.assertTrue(json.loads(ab.summary)["ok"])
        ts = self.highway.dispatch("store telemetry status", cwd=str(self.base))
        self.assertTrue(json.loads(ts.summary)["ok"])


if __name__ == "__main__":
    unittest.main()
