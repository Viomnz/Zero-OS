import json
import shutil
import socket
import sys
import tempfile
import threading
import time
import unittest
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from zero_os.native_shell_bridge import run_shell_bridge
from zero_os.native_shell_bridge import init_shell_bridge_auth


class NativeShellBridgeTests(unittest.TestCase):
    @staticmethod
    def _free_port() -> int:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            return int(sock.getsockname()[1])

    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_shell_bridge_")
        self.base = Path(self.tempdir)
        docs = self.base / "docs" / "kernel"
        docs.mkdir(parents=True, exist_ok=True)
        for name in (
            "README.md",
            "boot_trust_chain.md",
            "memory_manager.md",
            "scheduler.md",
            "syscall_abi.md",
            "interrupts_exceptions.md",
            "process_thread_model.md",
            "driver_framework.md",
        ):
            (docs / name).write_text("ok\n", encoding="utf-8")
        self.port = self._free_port()
        auth = init_shell_bridge_auth(str(self.base))
        self.assertTrue(auth["ok"])
        self.token = json.loads((self.base / ".zero_os" / "native_platform" / "shell_bridge_token.json").read_text(encoding="utf-8"))["token"]
        self.thread = threading.Thread(
            target=run_shell_bridge,
            args=(str(self.base), "127.0.0.1", self.port),
            daemon=True,
        )
        self.thread.start()
        time.sleep(0.5)

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def test_health_and_action(self) -> None:
        with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/healthz", timeout=5) as resp:
            health = json.loads(resp.read().decode("utf-8", errors="replace"))
        self.assertTrue(health["ok"])

        bad_req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/action",
            data=json.dumps({"command": "native platform status"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with self.assertRaises(Exception):
            urllib.request.urlopen(bad_req, timeout=5)

        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/action",
            data=json.dumps({"command": "native platform status"}).encode("utf-8"),
            headers={"Content-Type": "application/json", "X-Zero-Token": self.token},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            payload = json.loads(resp.read().decode("utf-8", errors="replace"))
        self.assertTrue(payload["ok"])
        self.assertEqual("system", payload["capability"])
        summary = json.loads(payload["summary"])
        self.assertTrue(summary["ok"])


if __name__ == "__main__":
    unittest.main()
