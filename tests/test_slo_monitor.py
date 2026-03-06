import json
import shutil
import tempfile
import unittest
from pathlib import Path

from ai_from_scratch.slo_monitor import evaluate_slo


class SloMonitorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_slo_monitor_")
        self.base = Path(self.tempdir)
        self.runtime = self.base / ".zero_os" / "runtime"
        self.runtime.mkdir(parents=True, exist_ok=True)
        (self.runtime / "zero_ai_tasks.txt").write_text("", encoding="utf-8")
        (self.runtime / "zero_ai_output.txt").write_text("ok", encoding="utf-8")
        (self.runtime / "zero_ai_heartbeat.json").write_text(
            json.dumps({"status": "running"}), encoding="utf-8"
        )

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_slo_ok_when_metrics_within_policy(self) -> None:
        out = evaluate_slo(str(self.base))
        self.assertTrue(out["ok"])
        self.assertEqual(out["violations"], [])
        report = self.runtime / "slo_report.json"
        self.assertTrue(report.exists())

    def test_slo_detects_violations(self) -> None:
        (self.runtime / "zero_ai_heartbeat.json").write_text(
            json.dumps({"status": "safe_mode"}), encoding="utf-8"
        )
        (self.runtime / "zero_ai_tasks.txt").write_text("\n".join(["x"] * 200), encoding="utf-8")
        out = evaluate_slo(str(self.base))
        self.assertFalse(out["ok"])
        self.assertGreaterEqual(len(out["violations"]), 1)


if __name__ == "__main__":
    unittest.main()
