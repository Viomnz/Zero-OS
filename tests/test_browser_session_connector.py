import json
import shutil
import sys
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from zero_os.fast_path_cache import clear_fast_path_cache
from zero_os.browser_session_connector import browser_session_open, browser_session_remember_page, browser_session_status


class BrowserSessionConnectorTests(unittest.TestCase):
    def setUp(self) -> None:
        clear_fast_path_cache(namespace="browser_session_status")
        self.tempdir = tempfile.mkdtemp(prefix="browser_session_connector_")
        self.base = Path(self.tempdir)

    def tearDown(self) -> None:
        clear_fast_path_cache(namespace="browser_session_status")
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def _session_path(self) -> Path:
        return self.base / ".zero_os" / "connectors" / "browser_session.json"

    def test_status_compacts_existing_duplicate_success_tabs(self) -> None:
        path = self._session_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "tabs": [
                        {"url": "https://example.com/", "opened": True},
                        {"url": "https://example.com", "opened": True},
                        {"url": "https://example.com/", "opened": True},
                    ],
                    "last_opened": "https://example.com/",
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        status = browser_session_status(str(self.base))

        self.assertEqual(1, len(status["tabs"]))
        self.assertEqual("https://example.com", status["tabs"][0]["url"])
        self.assertTrue(status["tabs"][0]["opened"])
        self.assertEqual("https://example.com", status["last_opened"])

    def test_open_reuses_existing_successful_tab(self) -> None:
        with patch("zero_os.browser_session_connector.webbrowser.open", return_value=True) as mocked_open:
            first = browser_session_open(str(self.base), "https://example.com/")
            second = browser_session_open(str(self.base), "https://example.com")

        self.assertTrue(first["opened"])
        self.assertFalse(first["reused_existing"])
        self.assertTrue(second["reused_existing"])
        self.assertEqual(1, mocked_open.call_count)

        status = browser_session_status(str(self.base))
        self.assertEqual(1, len(status["tabs"]))
        self.assertEqual("https://example.com", status["tabs"][0]["url"])
        self.assertTrue(status["tabs"][0]["opened"])
        self.assertEqual("https://example.com", status["last_opened"])
        self.assertEqual("https://example.com", status["active_tab"])

    def test_open_suppresses_rapid_duplicate_launches(self) -> None:
        with patch("zero_os.browser_session_connector.webbrowser.open", return_value=True) as mocked_open:
            first = browser_session_open(str(self.base), "https://example.com")
            second = browser_session_open(str(self.base), "https://example.com")
            third = browser_session_open(str(self.base), "https://example.com/")
            fourth = browser_session_open(str(self.base), "https://example.com")

        self.assertTrue(first["opened"])
        self.assertTrue(second["reused_existing"])
        self.assertTrue(third["reused_existing"])
        self.assertTrue(fourth["reused_existing"])
        self.assertEqual(1, mocked_open.call_count)

        status = browser_session_status(str(self.base))
        self.assertEqual(1, len(status["tabs"]))
        self.assertEqual("https://example.com", status["tabs"][0]["url"])

    def test_open_does_not_relaunch_when_browser_backend_returns_false(self) -> None:
        with patch("zero_os.browser_session_connector.webbrowser.open", return_value=False) as mocked_open:
            first = browser_session_open(str(self.base), "https://example.com")
            second = browser_session_open(str(self.base), "https://example.com/")
            third = browser_session_open(str(self.base), "https://example.com")

        self.assertTrue(first["opened"])
        self.assertTrue(first["launch_attempted"])
        self.assertFalse(first["launch_result"])
        self.assertTrue(second["reused_existing"])
        self.assertTrue(third["reused_existing"])
        self.assertEqual(1, mocked_open.call_count)

        status = browser_session_status(str(self.base))
        self.assertEqual(1, len(status["tabs"]))
        self.assertEqual("https://example.com", status["tabs"][0]["url"])
        self.assertTrue(status["tabs"][0]["launch_attempted"])

    def test_open_serializes_concurrent_duplicate_launches(self) -> None:
        start = threading.Barrier(6)
        call_count = 0
        call_count_lock = threading.Lock()

        def slow_open(url: str, new: int = 2) -> bool:
            nonlocal call_count
            with call_count_lock:
                call_count += 1
            time.sleep(0.05)
            return True

        def worker() -> dict:
            start.wait()
            return browser_session_open(str(self.base), "https://example.com/")

        with patch("zero_os.browser_session_connector.webbrowser.open", side_effect=slow_open):
            with ThreadPoolExecutor(max_workers=6) as pool:
                results = list(pool.map(lambda _: worker(), range(6)))

        self.assertEqual(1, call_count)
        self.assertEqual(1, sum(1 for result in results if not result["reused_existing"]))
        self.assertEqual(5, sum(1 for result in results if result["reused_existing"]))

        status = browser_session_status(str(self.base))
        self.assertEqual(1, len(status["tabs"]))
        self.assertEqual("https://example.com", status["tabs"][0]["url"])

    def test_remember_page_persists_page_memory(self) -> None:
        browser_session_remember_page(
            str(self.base),
            "https://example.com/",
            {"title": "Example Domain", "summary": "Example summary", "selectors": ["body", "a"], "links": [{"href": "/", "label": "home"}], "interactive": True},
        )

        status = browser_session_status(str(self.base))

        self.assertIn("https://example.com", status["page_memory"])
        self.assertEqual("Example Domain", status["page_memory"]["https://example.com"]["title"])

    def test_status_uses_fast_path_when_session_is_unchanged(self) -> None:
        first = browser_session_status(str(self.base))

        with patch("zero_os.browser_session_connector._build_browser_session_status", side_effect=AssertionError("should use cache")):
            second = browser_session_status(str(self.base))

        self.assertFalse(first["fast_path_cache"]["hit"])
        self.assertTrue(second["fast_path_cache"]["hit"])


if __name__ == "__main__":
    unittest.main()
