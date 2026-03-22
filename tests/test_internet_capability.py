import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from zero_os.api_connector_profiles import profile_set
from zero_os.internet_capability import internet_capability_status


class InternetCapabilityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_ai_internet_")
        self.base = Path(self.tempdir)
        (self.base / ".zero_os").mkdir(parents=True, exist_ok=True)
        (self.base / ".zero_os" / "state.json").write_text("{}\n", encoding="utf-8")

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_status_reports_internet_surfaces(self) -> None:
        profile_set(str(self.base), "demo", "https://example.com")

        status = internet_capability_status(str(self.base))

        self.assertTrue(status["ok"])
        self.assertTrue(status["summary"]["internet_ready"])
        self.assertEqual(1, status["api_profiles"]["count"])
        self.assertIn("demo", status["api_profiles"]["names"])
        self.assertEqual(1, status["summary"]["connected_surface_count"])

    def test_status_does_not_count_browser_surface_in_cold_workspace(self) -> None:
        status = internet_capability_status(str(self.base))

        self.assertTrue(status["ok"])
        self.assertFalse(status["browser"]["connected"])
        self.assertEqual(0, status["browser"]["tab_count"])
        self.assertEqual(0, status["browser"]["remembered_page_count"])
        self.assertEqual(0, status["summary"]["connected_surface_count"])
