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


class RealOsStatusTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_real_os_")
        self.base = Path(self.tempdir)
        self.highway = Highway(cwd=str(self.base))

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_real_os_status_default_overlay(self) -> None:
        out = self.highway.dispatch("real os status", cwd=str(self.base))
        data = json.loads(out.summary)
        self.assertTrue(data["ok"])
        self.assertEqual("hosted-overlay", data["classification"])

    def test_real_os_status_native_when_artifacts_exist(self) -> None:
        (self.base / "boot").mkdir(parents=True, exist_ok=True)
        (self.base / "kernel").mkdir(parents=True, exist_ok=True)
        (self.base / "drivers").mkdir(parents=True, exist_ok=True)
        (self.base / "scripts").mkdir(parents=True, exist_ok=True)
        (self.base / "boot/zero_boot.efi").write_text("x", encoding="utf-8")
        (self.base / "kernel/zero_kernel.elf").write_text("x", encoding="utf-8")
        (self.base / "boot/initramfs.img").write_text("x", encoding="utf-8")
        (self.base / "drivers/manifest.json").write_text("{}", encoding="utf-8")
        (self.base / "scripts/build_boot_media.ps1").write_text("echo build", encoding="utf-8")

        out = self.highway.dispatch("os reality status", cwd=str(self.base))
        data = json.loads(out.summary)
        self.assertEqual("prototype-native", data["classification"])
        self.assertEqual(100.0, data["real_os_readiness_score"])


if __name__ == "__main__":
    unittest.main()
