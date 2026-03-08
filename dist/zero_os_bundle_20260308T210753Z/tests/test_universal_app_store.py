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


class UniversalAppStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_store_")
        self.base = Path(self.tempdir)
        self.highway = Highway(cwd=str(self.base))

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_validate_publish_list_resolve(self) -> None:
        pkg = self.base / "app_package"
        (pkg / "builds").mkdir(parents=True, exist_ok=True)
        (pkg / "metadata").mkdir(parents=True, exist_ok=True)
        (pkg / "signature").mkdir(parents=True, exist_ok=True)
        (pkg / "builds" / "windows_x64.exe").write_bytes(b"exe")
        (pkg / "builds" / "linux_x64.bin").write_bytes(b"bin")
        (pkg / "builds" / "web.wasm").write_bytes(b"wasm")
        (pkg / "metadata" / "permissions.json").write_text(json.dumps({"camera": False}), encoding="utf-8")
        (pkg / "signature" / "developer.sig").write_text("signed", encoding="utf-8")
        manifest = {
            "name": "ExampleApp",
            "version": "1.0",
            "targets": {
                "windows": "builds/windows_x64.exe",
                "linux": "builds/linux_x64.bin",
                "web": "builds/web.wasm",
            },
        }
        (pkg / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

        v = self.highway.dispatch("store validate app_package", cwd=str(self.base))
        self.assertTrue(json.loads(v.summary)["ok"])
        p = self.highway.dispatch("store publish app_package", cwd=str(self.base))
        self.assertTrue(json.loads(p.summary)["ok"])
        lst = self.highway.dispatch("store list", cwd=str(self.base))
        self.assertEqual(1, json.loads(lst.summary)["total"])
        r = self.highway.dispatch("store resolve ExampleApp os=linux", cwd=str(self.base))
        rr = json.loads(r.summary)
        self.assertTrue(rr["ok"])
        self.assertEqual("linux", rr["os"])
        d = self.highway.dispatch("store client detect", cwd=str(self.base))
        self.assertTrue(json.loads(d.summary)["ok"])
        sc = self.highway.dispatch("store security scan ExampleApp", cwd=str(self.base))
        self.assertTrue(json.loads(sc.summary)["ok"])

    def test_resolve_with_fallback_web(self) -> None:
        pkg = self.base / "uap_pkg"
        (pkg / "builds").mkdir(parents=True, exist_ok=True)
        (pkg / "metadata").mkdir(parents=True, exist_ok=True)
        (pkg / "signature").mkdir(parents=True, exist_ok=True)
        (pkg / "builds" / "web.wasm").write_bytes(b"wasm")
        (pkg / "signature" / "developer.sig").write_text("signed", encoding="utf-8")
        manifest = {"name": "WebFirst", "version": "1.0", "targets": {"web": "builds/web.wasm"}}
        (pkg / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

        self.highway.dispatch("store publish uap_pkg", cwd=str(self.base))
        r = self.highway.dispatch("store resolve device WebFirst os=android cpu=arm64 arch=arm64 security=strict", cwd=str(self.base))
        data = json.loads(r.summary)
        self.assertTrue(data["ok"])
        self.assertEqual("fallback-web", data["delivery"])


if __name__ == "__main__":
    unittest.main()
