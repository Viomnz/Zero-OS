import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from zero_os.triad_balance import run_triad_balance, triad_ops_set, triad_ops_status, triad_ops_tick


class TriadBalanceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_triad_balance_")
        self.base = Path(self.tempdir)

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_triad_ops_status_defaults(self) -> None:
        status = triad_ops_status(str(self.base))

        self.assertFalse(status["enabled"])
        self.assertGreaterEqual(int(status["interval_seconds"]), 30)
        self.assertEqual("log+inbox", status["alert_sink"])

    def test_triad_ops_tick_runs_when_enabled(self) -> None:
        triad_ops_set(str(self.base), True, 120, "log")

        tick = triad_ops_tick(str(self.base))

        self.assertTrue(tick["ok"])
        self.assertTrue(tick["ran"])
        self.assertTrue(tick["ops"]["enabled"])
        self.assertEqual(120, tick["ops"]["interval_seconds"])

        report = run_triad_balance(str(self.base))
        self.assertTrue(report["ok"])
        self.assertIn("triad_score", report)
        self.assertIn("antivirus_monitor", report)


if __name__ == "__main__":
    unittest.main()
