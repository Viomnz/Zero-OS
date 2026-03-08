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
from zero_os.native_platform import maximize, status


class NativePlatformTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_native_platform_")
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
            (docs / name).write_text(f"{name}\n", encoding="utf-8")

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_native_platform_maximize_builds_integrated_state(self) -> None:
        before = status(str(self.base))
        self.assertTrue(before["ok"])
        self.assertTrue((self.base / ".zero_os" / "native_platform" / "status.json").exists())
        out = maximize(str(self.base))
        self.assertTrue(out["ok"])
        after = out["status"]
        self.assertTrue(after["categories"]["real_kernel_execution_on_hardware"])
        self.assertTrue(after["categories"]["full_driver_coverage"])
        self.assertTrue(after["categories"]["filesystem_and_network_stack"])
        self.assertTrue(after["categories"]["desktop_session_depth"])
        self.assertTrue(after["categories"]["production_backend_deployment"])
        self.assertTrue(after["categories"]["end_user_apps_ecosystem_depth"])
        self.assertGreaterEqual(after["score"], before["score"])
        self.assertTrue((self.base / ".zero_os" / "native_platform" / "maximize_report.json").exists())
        self.assertTrue((self.base / ".zero_os" / "native_platform" / "status.json").exists())

    def test_system_commands_for_platform_and_desktop(self) -> None:
        maxed = self.highway.dispatch("native platform maximize", cwd=str(self.base))
        self.assertTrue(json.loads(maxed.summary)["ok"])
        desktop = self.highway.dispatch(
            "native desktop session set session=zero-desktop wm=layered-wm start=layered",
            cwd=str(self.base),
        )
        self.assertTrue(json.loads(desktop.summary)["ok"])
        win = self.highway.dispatch("native desktop window open app=Zero Files layer=top", cwd=str(self.base))
        wdata = json.loads(win.summary)
        self.assertTrue(wdata["ok"])
        self.assertIn("pid", wdata["window"])
        comp = self.highway.dispatch(
            "native compositor set mode=layer-compositor effects=snap,stack,blur",
            cwd=str(self.base),
        )
        self.assertTrue(json.loads(comp.summary)["ok"])
        relayer = self.highway.dispatch(
            "native desktop window layer app=Zero Files layer=overlay",
            cwd=str(self.base),
        )
        self.assertTrue(json.loads(relayer.summary)["ok"])
        action = self.highway.dispatch(
            "native desktop window action app=Zero Files action=maximize",
            cwd=str(self.base),
        )
        self.assertTrue(json.loads(action.summary)["ok"])
        st = self.highway.dispatch("native platform status", cwd=str(self.base))
        sdata = json.loads(st.summary)
        self.assertTrue(sdata["ok"])
        self.assertEqual("layered-wm", sdata["desktop"]["window_manager"])
        self.assertEqual("layer-compositor", sdata["desktop"]["compositor"]["mode"])
        self.assertEqual("maximized", sdata["desktop"]["windows"][0]["state"])
        close = self.highway.dispatch(
            "native desktop window action app=Zero Files action=close",
            cwd=str(self.base),
        )
        self.assertTrue(json.loads(close.summary)["ok"])
        st2 = self.highway.dispatch("kernel stack status", cwd=str(self.base))
        kdata = json.loads(st2.summary)
        self.assertEqual("exited", kdata["processes"]["table"][0]["state"])


if __name__ == "__main__":
    unittest.main()
