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

from zero_os.api_connector_profiles import profile_set, profile_status
from zero_os.fast_path_cache import clear_fast_path_cache
from zero_os.github_integration_pack import connect_repo, status as github_status


class StatusFastPathTests(unittest.TestCase):
    def setUp(self) -> None:
        clear_fast_path_cache(namespace="api_profile_status")
        clear_fast_path_cache(namespace="github_integration_status")
        self.tempdir = tempfile.mkdtemp(prefix="status_fast_paths_")
        self.base = Path(self.tempdir)

    def tearDown(self) -> None:
        clear_fast_path_cache(namespace="api_profile_status")
        clear_fast_path_cache(namespace="github_integration_status")
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_api_profile_status_uses_fast_path_when_unchanged(self) -> None:
        profile_set(str(self.base), "demo", "https://example.com")
        first = profile_status(str(self.base))

        with patch("zero_os.api_connector_profiles._build_profile_status", side_effect=AssertionError("should use cache")):
            second = profile_status(str(self.base))

        self.assertFalse(first["fast_path_cache"]["hit"])
        self.assertTrue(second["fast_path_cache"]["hit"])
        self.assertIn("demo", second["profiles"])

    def test_github_status_uses_fast_path_when_unchanged(self) -> None:
        connect_repo(str(self.base), "owner/repo")
        first = github_status(str(self.base))

        with patch("zero_os.github_integration_pack._build_status", side_effect=AssertionError("should use cache")):
            second = github_status(str(self.base))

        self.assertFalse(first["fast_path_cache"]["hit"])
        self.assertTrue(second["fast_path_cache"]["hit"])
        self.assertIn("owner/repo", second["repos"])


if __name__ == "__main__":
    unittest.main()
