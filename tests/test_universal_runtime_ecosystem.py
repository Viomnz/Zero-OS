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


class UniversalRuntimeEcosystemTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_ure_")
        self.base = Path(self.tempdir)
        self.highway = Highway(cwd=str(self.base))

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_runtime_and_adapters(self) -> None:
        i = self.highway.dispatch("universal runtime install version=1.0", cwd=str(self.base))
        self.assertTrue(json.loads(i.summary)["ok"])
        s = self.highway.dispatch("universal runtime status", cwd=str(self.base))
        self.assertTrue(json.loads(s.summary)["runtime"]["installed"])
        a = self.highway.dispatch("universal adapter set linux LinuxAdapterV2", cwd=str(self.base))
        self.assertTrue(json.loads(a.summary)["ok"])
        st = self.highway.dispatch("universal adapters status", cwd=str(self.base))
        self.assertEqual("LinuxAdapterV2", json.loads(st.summary)["adapters"]["linux"])

    def test_execution_flow_with_store(self) -> None:
        pkg = self.base / "app_pkg"
        (pkg / "builds").mkdir(parents=True, exist_ok=True)
        (pkg / "metadata").mkdir(parents=True, exist_ok=True)
        (pkg / "signature").mkdir(parents=True, exist_ok=True)
        (pkg / "builds" / "linux_x64.bin").write_bytes(b"bin")
        (pkg / "signature" / "developer.sig").write_text("sig", encoding="utf-8")
        manifest = {"name": "FlowApp", "version": "1.0", "targets": {"linux": "builds/linux_x64.bin"}}
        (pkg / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

        self.highway.dispatch("store publish app_pkg", cwd=str(self.base))
        flow = self.highway.dispatch("universal execution flow FlowApp os=linux", cwd=str(self.base))
        data = json.loads(flow.summary)
        self.assertTrue(data["ok"])
        self.assertEqual("linux", data["resolve"]["os"])

    def test_security_infra_coverage(self) -> None:
        sec = self.highway.dispatch("universal security status", cwd=str(self.base))
        inf = self.highway.dispatch("universal infrastructure status", cwd=str(self.base))
        cov = self.highway.dispatch("universal ecosystem coverage", cwd=str(self.base))
        self.assertTrue(json.loads(sec.summary)["ok"])
        self.assertTrue(json.loads(inf.summary)["ok"])
        self.assertTrue(json.loads(cov.summary)["ok"])


if __name__ == "__main__":
    unittest.main()
