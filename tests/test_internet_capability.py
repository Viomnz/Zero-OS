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

from zero_os.fast_path_cache import clear_fast_path_cache
from zero_os.api_connector_profiles import profile_set
from zero_os.internet_capability import internet_capability_status


class InternetCapabilityTests(unittest.TestCase):
    def setUp(self) -> None:
        clear_fast_path_cache(namespace="browser_session_status")
        clear_fast_path_cache(namespace="browser_dom_status")
        clear_fast_path_cache(namespace="api_profile_status")
        clear_fast_path_cache(namespace="github_integration_status")
        clear_fast_path_cache(namespace="internet_capability_status")
        self.tempdir = tempfile.mkdtemp(prefix="zero_ai_internet_")
        self.base = Path(self.tempdir)
        (self.base / ".zero_os").mkdir(parents=True, exist_ok=True)
        (self.base / ".zero_os" / "state.json").write_text("{}\n", encoding="utf-8")

    def tearDown(self) -> None:
        clear_fast_path_cache(namespace="browser_session_status")
        clear_fast_path_cache(namespace="browser_dom_status")
        clear_fast_path_cache(namespace="api_profile_status")
        clear_fast_path_cache(namespace="github_integration_status")
        clear_fast_path_cache(namespace="internet_capability_status")
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

    def test_status_uses_fast_path_when_inputs_are_unchanged(self) -> None:
        first = internet_capability_status(str(self.base))

        with patch("zero_os.internet_capability._build_internet_capability_status", side_effect=AssertionError("should use cache")):
            second = internet_capability_status(str(self.base))

        self.assertFalse(first["fast_path_cache"]["hit"])
        self.assertTrue(second["fast_path_cache"]["hit"])
        self.assertEqual(first["summary"]["connected_surface_count"], second["summary"]["connected_surface_count"])

    def test_status_reports_per_surface_cache_metrics_when_rebuilt(self) -> None:
        profile_set(str(self.base), "demo", "https://example.com")
        first = internet_capability_status(str(self.base))
        clear_fast_path_cache(namespace="internet_capability_status")
        second = internet_capability_status(str(self.base))

        self.assertEqual(4, first["summary"]["surface_cache_total_count"])
        self.assertIn("browser_session", first["cache_surfaces"])
        self.assertIn("browser_dom", first["cache_surfaces"])
        self.assertIn("api_profiles", first["cache_surfaces"])
        self.assertIn("github_integration", first["cache_surfaces"])
        self.assertEqual(4, second["summary"]["surface_cache_hit_count"])
