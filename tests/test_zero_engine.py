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
from zero_os.zero_engine_adapters import ZeroEngineAdapter, register_zero_engine_adapter, unregister_zero_engine_adapter


class ZeroEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_engine_")
        self.base = Path(self.tempdir)
        (self.base / "src").mkdir(parents=True, exist_ok=True)
        (self.base / "src" / "main.py").write_text("print('ok')\n", encoding="utf-8")
        (self.base / "README.md").write_text("# Zero\n", encoding="utf-8")

    def tearDown(self) -> None:
        unregister_zero_engine_adapter("unit_observer")
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_zero_engine_tick_runs_subsystems_and_persists_state(self) -> None:
        report = zero_engine_tick(str(self.base), force=True, runtime_context={"continuity_ready": True, "pressure_ready": True})
        status = zero_engine_status(str(self.base))

        self.assertTrue(report["ok"])
        self.assertEqual("parallel", report["latest_report"]["scan_mode"])
        self.assertIn("scan_snapshot", report["latest_report"])
        self.assertIn("antivirus", report["latest_report"]["subsystems"])
        self.assertIn("pressure", report["latest_report"]["subsystems"])
        self.assertIn("recovery", report["latest_report"]["subsystems"])
        self.assertIn("resilience", report["latest_report"]["subsystems"])
        self.assertIn("self_derivation", report["latest_report"]["subsystems"])
        self.assertTrue((self.base / ".zero_os" / "runtime" / "zero_engine_status.json").exists())
        self.assertTrue((self.base / ".zero_os" / "runtime" / "workspace_scan_snapshot.json").exists())
        self.assertEqual(report["last_run_utc"], status["last_run_utc"])

    def test_zero_engine_status_exposes_extended_builtin_adapter_set(self) -> None:
        status = zero_engine_status(str(self.base))

        self.assertGreaterEqual(int(status["adapter_count"]), 6)
        self.assertIn("pressure", status["adapter_names"])
        self.assertIn("self_derivation", status["adapter_names"])

    def test_zero_engine_creates_recovery_baseline_when_missing(self) -> None:
        report = zero_engine_tick(str(self.base), force=True, runtime_context={"continuity_ready": True, "pressure_ready": True})
        recovery = report["latest_report"]["subsystems"]["recovery"]

        self.assertTrue(recovery["ran"])
        self.assertEqual("backup", recovery["decision"]["action"])
        self.assertTrue(recovery["result"]["ok"])
        self.assertTrue((self.base / ".zero_os" / "production" / "snapshots").exists())

    def test_zero_engine_uses_registered_adapters(self) -> None:
        register_zero_engine_adapter(
            ZeroEngineAdapter(
                name="unit_observer",
                interval_seconds=60,
                scan=lambda cwd, scan_snapshot=None: {"missing": False, "seen": True},
                decide=lambda cwd, facts, runtime_context=None: {"action": "observe", "reason": "unit", "confidence": 0.6},
                enforce=lambda cwd, decision, facts: {"ok": True, "action": decision["action"], "seen": bool(facts.get("seen", False))},
            )
        )

        report = zero_engine_tick(str(self.base), force=True, runtime_context={"continuity_ready": True, "pressure_ready": True})

        self.assertIn("unit_observer", report["adapter_names"])
        self.assertIn("unit_observer", report["latest_report"]["subsystems"])
        self.assertEqual("observe", report["latest_report"]["subsystems"]["unit_observer"]["decision"]["action"])
