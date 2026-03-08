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
from zero_os.autonomous_fix_gate import _history_path, _load_history
from zero_os.autonomous_fix_gate import autonomy_status
from zero_os.recovery import zero_ai_backup_create


class AutonomousFixGateSystemTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_autonomy_system_")
        self.base = Path(self.tempdir)
        (self.base / ".zero_os").mkdir(parents=True, exist_ok=True)
        (self.base / ".zero_os" / "state.json").write_text("{}", encoding="utf-8")
        self.highway = Highway(cwd=str(self.base))

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_zero_ai_autonomy_status_dispatch(self) -> None:
        out = self.highway.dispatch("zero ai autonomy status", cwd=str(self.base))
        data = json.loads(out.summary)
        self.assertTrue(data["ok"])
        self.assertIn("thresholds", data)

    def test_fix_all_now_blocked_without_rollback(self) -> None:
        out = self.highway.dispatch("fix all now", cwd=str(self.base))
        data = json.loads(out.summary)
        self.assertFalse(data["ok"])
        self.assertEqual("autonomy_gate", data["reason"])

    def test_fix_all_now_runs_with_recovery_snapshot(self) -> None:
        zero_ai_backup_create(str(self.base))
        out = self.highway.dispatch("fix all now", cwd=str(self.base))
        data = json.loads(out.summary)
        self.assertTrue(data["ok"])
        self.assertEqual("allow", data["gate"]["decision"])

    def test_recovery_records_autonomy_history(self) -> None:
        zero_ai_backup_create(str(self.base))
        self.highway.dispatch("zero ai recover", cwd=str(self.base))
        status = autonomy_status(str(self.base))
        self.assertGreaterEqual(status["history_events"], 1)
        events = _load_history(str(self.base))["events"]
        self.assertIn("health_before", events[-1])
        self.assertIn("health_after", events[-1])


if __name__ == "__main__":
    unittest.main()
