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

from zero_os.browser_dom_automation import act, inspect_page, status


class BrowserDomAutomationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="browser_dom_automation_")
        self.base = Path(self.tempdir)

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_inspect_page_extracts_real_page_summary(self) -> None:
        html = "<html><head><title>Example Domain</title></head><body><main id='main'><a href='/more'>More</a><form action='/submit'><input name='q'></form></main></body></html>"
        with patch("zero_os.browser_dom_automation.request_text", return_value={"ok": True, "status": 200, "body": html}):
            result = inspect_page(str(self.base), "https://example.com")

        page = result["page"]
        self.assertEqual("Example Domain", page["title"])
        self.assertIn("#main", page["selectors"])
        self.assertEqual(1, len(page["links"]))
        self.assertEqual(1, len(page["forms"]))

    def test_act_uses_inspected_page_memory_for_selector_matching(self) -> None:
        html = "<html><head><title>Example Domain</title></head><body><button id='submit-btn'>Submit</button></body></html>"
        with patch("zero_os.browser_dom_automation.request_text", return_value={"ok": True, "status": 200, "body": html}):
            inspect_page(str(self.base), "https://example.com")
            result = act(str(self.base), "https://example.com", "click", "#submit-btn")

        self.assertTrue(result["action"]["selector_found"])
        self.assertEqual("#submit-btn", result["action"]["selector"])
        dom = status(str(self.base))
        self.assertEqual("https://example.com", dom["last_page"])

    def test_inspect_page_returns_failure_when_fetch_fails(self) -> None:
        with patch("zero_os.browser_dom_automation.request_text", return_value={"ok": False, "status": 503, "error": "upstream_down"}):
            result = inspect_page(str(self.base), "https://example.com")

        self.assertFalse(result["ok"])
        self.assertEqual("upstream_down", result["reason"])
        self.assertFalse(result["page"]["ok"])

    def test_act_refuses_to_run_when_page_fetch_fails(self) -> None:
        with patch("zero_os.browser_dom_automation.request_text", return_value={"ok": False, "status": 503, "error": "upstream_down"}):
            result = act(str(self.base), "https://example.com", "click", "#submit-btn")

        self.assertFalse(result["ok"])
        self.assertEqual("upstream_down", result["reason"])
