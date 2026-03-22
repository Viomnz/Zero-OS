import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from zero_os.maintenance_orchestrator import maintenance_run, maintenance_status


class MaintenanceOrchestratorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_ai_maintenance_")
        self.base = Path(self.tempdir)
        (self.base / ".zero_os").mkdir(parents=True, exist_ok=True)
        (self.base / ".zero_os" / "state.json").write_text("{}\n", encoding="utf-8")

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_status_prioritizes_runtime_when_runtime_is_missing(self) -> None:
        status = maintenance_status(str(self.base))

        self.assertTrue(status["ok"])
        self.assertEqual("runtime_run", status["next_action"]["action"])
        self.assertIn("phase runtime", status["next_action"]["summary"].lower())

    def test_run_executes_runtime_when_runtime_is_missing(self) -> None:
        result = maintenance_run(str(self.base))

        self.assertTrue(result["ok"])
        self.assertEqual("runtime_run", result["action"])
        self.assertTrue((self.base / ".zero_os" / "runtime" / "phase_runtime_status.json").exists())

    def test_run_prefers_pressure_refresh_when_runtime_is_ready_and_flow_is_clean(self) -> None:
        snapshot = {
            "runtime": {"ok": True, "runtime_ready": True, "missing": False},
            "flow": {"ok": True, "last_scan_utc": "2026-03-19T00:00:00+00:00", "summary": {"flow_score": 100.0}},
            "pressure": {"ok": True, "missing": True, "overall_score": 0.0},
            "contradiction": {"continuity": {"same_system": True, "has_contradiction": False}},
            "workflows": {"lanes": {"self_repair": {"ready": True, "active": True}}},
            "backups": {"snapshot_count": 1},
            "self_repair": {"enabled": False},
        }
        with patch("zero_os.maintenance_orchestrator._snapshot", return_value=snapshot):
            result = maintenance_run(str(self.base))

        self.assertTrue(result["ok"])
        self.assertEqual("pressure_run", result["action"])
