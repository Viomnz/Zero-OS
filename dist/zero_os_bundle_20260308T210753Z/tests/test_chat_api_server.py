import json
import socket
import shutil
import tempfile
import threading
import time
import unittest
import urllib.request
import urllib.error
from pathlib import Path

from ai_from_scratch.chat_api_server import run_chat_api


class ChatApiServerTests(unittest.TestCase):
    @staticmethod
    def _free_port() -> int:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            return int(sock.getsockname()[1])

    def setUp(self) -> None:
        self.tempdir = tempfile.mkdtemp(prefix="zero_chat_api_")
        self.base = Path(self.tempdir)
        (self.base / ".zero_os" / "runtime").mkdir(parents=True, exist_ok=True)
        self.port = self._free_port()
        self.server_thread = threading.Thread(
            target=run_chat_api,
            args=(self.base, "127.0.0.1", self.port),
            daemon=True,
        )
        self.server_thread.start()
        time.sleep(0.8)
        self.responder = threading.Thread(target=self._fake_daemon, daemon=True)
        self.responder.start()

    def tearDown(self) -> None:
        shutil.rmtree(self.tempdir, ignore_errors=True)

    def _fake_daemon(self) -> None:
        runtime = self.base / ".zero_os" / "runtime"
        req = runtime / "chat_requests.jsonl"
        resp = runtime / "chat_responses.jsonl"
        seen = set()
        while True:
            if not req.exists():
                time.sleep(0.1)
                continue
            for raw in req.read_text(encoding="utf-8", errors="replace").splitlines():
                try:
                    payload = json.loads(raw)
                except Exception:
                    continue
                rid = str(payload.get("request_id", ""))
                if not rid or rid in seen:
                    continue
                seen.add(rid)
                out = {
                    "request_id": rid,
                    "session_id": payload.get("session_id", "default"),
                    "turn_id": payload.get("turn_id", ""),
                    "status": "ok",
                    "output": "ack:" + str(payload.get("content", ""))[:24],
                }
                with resp.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(out) + "\n")
            time.sleep(0.1)

    def _post_json(self, path: str, payload: dict, headers: dict | None = None) -> dict:
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", **(headers or {})},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))

    def test_healthz(self) -> None:
        with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/healthz", timeout=5) as resp:
            payload = json.loads(resp.read().decode("utf-8", errors="replace"))
        self.assertTrue(payload["ok"])

    def test_completions_and_idempotency(self) -> None:
        body = {"tenant_id": "t1", "session_id": "s1", "message": "hello"}
        h = {"Idempotency-Key": "idem-1"}
        a = self._post_json("/v1/chat/completions", body, h)
        b = self._post_json("/v1/chat/completions", body, h)
        self.assertTrue(a["ok"])
        self.assertEqual(a["request_id"], b["request_id"])
        self.assertEqual(a["session_id"], "s1")
        self.assertEqual(a["tenant_id"], "t1")

    def test_auto_session_id_and_message_ids(self) -> None:
        body = {"tenant_id": "t1", "message": "hello autosession"}
        out = self._post_json("/v1/chat/completions", body)
        self.assertTrue(out["ok"])
        self.assertTrue(bool(out.get("session_id")))
        self.assertTrue(bool(out.get("message_id")))
        self.assertTrue(bool(out.get("parent_user_message_id")))

    def test_regenerate_and_continue_actions(self) -> None:
        base = self._post_json("/v1/chat/completions", {"tenant_id": "t1", "session_id": "s2", "message": "seed content"})
        self.assertTrue(base["ok"])
        regen = self._post_json("/v1/chat/completions", {"tenant_id": "t1", "session_id": "s2", "action": "regenerate"})
        self.assertTrue(regen["ok"])
        self.assertEqual("regenerate", regen.get("action"))
        cont = self._post_json("/v1/chat/completions", {"tenant_id": "t1", "session_id": "s2", "action": "continue"})
        self.assertTrue(cont["ok"])
        self.assertEqual("continue", cont.get("action"))

    def test_stream_endpoint_emits_done(self) -> None:
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/v1/chat/stream",
            data=json.dumps({"tenant_id": "t1", "session_id": "s3", "message": "stream hello"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            text = resp.read().decode("utf-8", errors="replace")
        self.assertIn("data: [DONE]", text)


if __name__ == "__main__":
    unittest.main()
