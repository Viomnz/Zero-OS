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

from zero_os.flow_monitor import flow_scan, flow_status


class FlowMonitorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_flow_monitor_")
        self.base = Path(self.tempdir)

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_flow_status_prompts_for_baseline_scan_before_first_run(self) -> None:
        status = flow_status(str(self.base))

        self.assertTrue(status["ok"])
        self.assertFalse(status["summary"]["source_scan_available"])
        self.assertTrue(any("zero ai flow scan" in step.lower() for step in status["highest_value_steps"]))

    def test_flow_scan_detects_syntax_and_antivirus_findings(self) -> None:
        (self.base / "bad.py").write_text(
            "print('EICAR-STANDARD-ANTIVIRUS-TEST-FILE')\nif True print('broken')\n",
            encoding="utf-8",
        )

        out = flow_scan(str(self.base), ".")

        self.assertTrue(out["ok"])
        self.assertGreater(out["summary"]["issue_count"], 0)
        self.assertGreater(out["report"]["source_integrity"]["syntax_error_count"], 0)
        self.assertGreater(out["report"]["antivirus_scan"]["finding_count"], 0)
        self.assertTrue((self.base / "bad.py").exists())

    def test_flow_scan_suppresses_known_security_fixture_noise(self) -> None:
        raw_scan = {
            "ok": True,
            "target": ".",
            "scanned_files": 3,
            "finding_count": 2,
            "process_finding_count": 1,
            "highest_severity": "critical",
            "findings": [
                {
                    "path": "src/zero_os/antivirus.py",
                    "severity": "critical",
                    "signature_hits": [{"id": "EICAR-SIM", "severity": "high"}],
                    "archive_hits": [],
                    "heuristic_score": 100,
                    "heuristic_reasons": ["encoded_payload"],
                },
                {
                    "path": "tests/test_antivirus_system.py",
                    "severity": "high",
                    "signature_hits": [{"id": "QVIR-SIM", "severity": "high"}],
                    "archive_hits": [],
                    "heuristic_score": 45,
                    "heuristic_reasons": ["quantum_marker"],
                },
            ],
            "process_findings": [
                {
                    "process": "powershell.exe",
                    "severity": "medium",
                    "reason": "suspicious_process_name",
                }
            ],
        }
        contradiction = {
            "active": True,
            "ready": True,
            "continuity": {"same_system": True, "has_contradiction": False},
        }
        health = {"health_score": 100.0}

        with (
            patch("zero_os.flow_monitor.scan_target_readonly", return_value=raw_scan),
            patch("zero_os.flow_monitor.contradiction_engine_status", return_value=contradiction),
            patch("zero_os.flow_monitor.capture_health_snapshot", return_value=health),
            patch("zero_os.flow_monitor.antivirus_monitor_status", return_value={"enabled": False}),
            patch("zero_os.flow_monitor.antivirus_agent_status", return_value={"ok": True}),
            patch("zero_os.flow_monitor.antivirus_quarantine_list", return_value={"ok": True, "count": 0, "items": []}),
        ):
            out = flow_scan(str(self.base), ".")

        self.assertTrue(out["ok"])
        self.assertEqual(0, out["report"]["antivirus_scan"]["finding_count"])
        self.assertEqual(0, out["report"]["antivirus_scan"]["process_finding_count"])
        self.assertEqual(0, out["summary"]["issue_count"])
        self.assertEqual(
            2,
            out["report"]["antivirus_scan"]["noise_control"]["suppressed_finding_count"],
        )
        self.assertEqual(
            1,
            out["report"]["antivirus_scan"]["noise_control"]["suppressed_process_finding_count"],
        )


if __name__ == "__main__":
    unittest.main()
