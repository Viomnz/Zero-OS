import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from zero_os.zero_engine import zero_engine_status, zero_engine_tick


class ZeroEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_engine_")
        self.base = Path(self.tempdir)
        (self.base / "src").mkdir(parents=True, exist_ok=True)
        (self.base / "src" / "main.py").write_text("print('ok')\n", encoding="utf-8")
        (self.base / "README.md").write_text("# Zero\n", encoding="utf-8")

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_zero_engine_tick_runs_subsystems_and_persists_state(self) -> None:
        report = zero_engine_tick(str(self.base), force=True, runtime_context={"continuity_ready": True, "pressure_ready": True})
        status = zero_engine_status(str(self.base))

        self.assertTrue(report["ok"])
        self.assertIn("antivirus", report["latest_report"]["subsystems"])
        self.assertIn("recovery", report["latest_report"]["subsystems"])
        self.assertIn("resilience", report["latest_report"]["subsystems"])
        self.assertTrue((self.base / ".zero_os" / "runtime" / "zero_engine_status.json").exists())
        self.assertEqual(report["last_run_utc"], status["last_run_utc"])

    def test_zero_engine_creates_recovery_baseline_when_missing(self) -> None:
        report = zero_engine_tick(str(self.base), force=True, runtime_context={"continuity_ready": True, "pressure_ready": True})
        recovery = report["latest_report"]["subsystems"]["recovery"]

        self.assertTrue(recovery["ran"])
        self.assertEqual("backup", recovery["decision"]["action"])
        self.assertTrue(recovery["result"]["ok"])
        self.assertTrue((self.base / ".zero_os" / "production" / "snapshots").exists())
