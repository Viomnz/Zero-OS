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


class ProductionPlatformOpsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_prod_platform_")
        self.base = Path(self.tempdir)
        self.highway = Highway(cwd=str(self.base))
        docs = self.base / "docs" / "kernel"
        docs.mkdir(parents=True, exist_ok=True)
        for name in (
            "README.md",
            "boot_trust_chain.md",
            "memory_manager.md",
            "scheduler.md",
            "syscall_abi.md",
            "interrupts_exceptions.md",
            "process_thread_model.md",
            "driver_framework.md",
        ):
            (docs / name).write_text("ok\n", encoding="utf-8")

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_production_platform_maximize(self) -> None:
        out = self.highway.dispatch("production platform maximize app=ZeroFiles version=1.0.0", cwd=str(self.base))
        data = json.loads(out.summary)
        self.assertTrue(data["ok"])
        self.assertIn("signed_native_lane", data)
        self.assertIn("backend_deploy_posture", data)
        self.assertIn("desktop_ux_loop", data)
        self.assertTrue((self.base / ".zero_os" / "production_platform" / "maximize.json").exists())

    def test_production_platform_subflows(self) -> None:
        backend = self.highway.dispatch("production platform backend deploy", cwd=str(self.base))
        self.assertTrue(json.loads(backend.summary)["ok"])
        desktop = self.highway.dispatch("production platform desktop ux", cwd=str(self.base))
        ddata = json.loads(desktop.summary)
        self.assertTrue(ddata["ok"])
        self.assertTrue(ddata["desktop"]["window_count"] >= 3)
        kernel = self.highway.dispatch("production platform kernel depth", cwd=str(self.base))
        self.assertTrue(json.loads(kernel.summary)["ok"])
        compat = self.highway.dispatch("production platform compatibility app=ZeroFiles", cwd=str(self.base))
        self.assertTrue(json.loads(compat.summary)["ok"])


if __name__ == "__main__":
    unittest.main()
