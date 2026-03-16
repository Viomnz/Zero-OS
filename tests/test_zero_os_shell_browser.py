import http.server
import os
import re
import socketserver
import subprocess
import threading
import time
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SHELL_HTML = ROOT / "zero_os_shell.html"
CHROME_CANDIDATES = [
    Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
    Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
    Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
    Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
]


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        return


def find_browser():
    for candidate in CHROME_CANDIDATES:
        if candidate.exists():
            return candidate
    return None


@pytest.mark.skipif(not SHELL_HTML.exists(), reason="Zero OS shell HTML is missing")
def test_zero_os_shell_renders_launcher_state_in_browser():
    browser = find_browser()
    if browser is None:
      pytest.skip("No Chrome/Edge browser installed for headless UI smoke test")

    previous_cwd = Path.cwd()
    os.chdir(ROOT)
    httpd = socketserver.TCPServer(("127.0.0.1", 8767), QuietHandler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        time.sleep(1.5)
        result = subprocess.run(
            [
                str(browser),
                "--headless=new",
                "--disable-gpu",
                "--virtual-time-budget=8000",
                "--dump-dom",
                "http://127.0.0.1:8767/zero_os_shell.html",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr[:1000]
        dom = result.stdout
        assert re.search(r"App Library", dom)
        assert re.search(r"Pinned Apps", dom)
        assert re.search(r"Zero Runtime", dom)
        assert re.search(r"Installed 0[.]9", dom)
        assert re.search(r"Published 1[.]0", dom)
        assert re.search(r"Update available", dom)
        assert re.search(r">Pin<|>Unpin<", dom)
        assert re.search(r"Local Mods", dom)
        assert re.search(r"Install Path", dom)
        assert re.search(r"Open Plugins", dom)
    finally:
        httpd.shutdown()
        httpd.server_close()
        os.chdir(previous_cwd)
