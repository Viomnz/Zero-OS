from __future__ import annotations

import json
import secrets
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse

from zero_os.highway import Highway


def _bridge_root(cwd: str) -> Path:
    p = Path(cwd).resolve() / ".zero_os" / "native_platform"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _token_path(cwd: str) -> Path:
    return _bridge_root(cwd) / "shell_bridge_token.json"


def _config_js_path(cwd: str) -> Path:
    return Path(cwd).resolve() / "zero_os_shell_bridge_config.js"


def init_shell_bridge_auth(cwd: str) -> dict:
    token = secrets.token_hex(24)
    _token_path(cwd).write_text(json.dumps({"token": token}, indent=2) + "\n", encoding="utf-8")
    _config_js_path(cwd).write_text(f'window.ZERO_SHELL_BRIDGE_TOKEN = "{token}";\n', encoding="utf-8")
    return {"ok": True, "token_path": str(_token_path(cwd)), "config_js": str(_config_js_path(cwd))}


def _load_token(cwd: str) -> str:
    p = _token_path(cwd)
    if not p.exists():
        init_shell_bridge_auth(cwd)
    try:
        return str(json.loads(p.read_text(encoding="utf-8", errors="replace")).get("token", ""))
    except Exception:
        init_shell_bridge_auth(cwd)
        return str(json.loads(p.read_text(encoding="utf-8", errors="replace")).get("token", ""))


def run_shell_bridge(cwd: str, host: str = "127.0.0.1", port: int = 8766) -> dict:
    base = str(Path(cwd).resolve())
    highway = Highway(cwd=base)
    token = _load_token(base)

    class Handler(BaseHTTPRequestHandler):
        def _write(self, code: int, payload: dict) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
            self.end_headers()
            self.wfile.write(body)

        def do_OPTIONS(self) -> None:
            self._write(200, {"ok": True})

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path == "/healthz":
                self._write(200, {"ok": True, "service": "zero-shell-bridge", "cwd": base})
                return
            self._write(404, {"ok": False, "reason": "not found"})

        def do_POST(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path != "/action":
                self._write(404, {"ok": False, "reason": "not found"})
                return
            provided = self.headers.get("X-Zero-Token", "").strip()
            if not provided or provided != token:
                self._write(401, {"ok": False, "reason": "unauthorized"})
                return
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length) if length > 0 else b"{}"
            try:
                payload = json.loads(raw.decode("utf-8", errors="replace"))
            except Exception:
                self._write(400, {"ok": False, "reason": "invalid json"})
                return
            command = str(payload.get("command", "")).strip()
            if not command:
                self._write(400, {"ok": False, "reason": "command required"})
                return
            result = highway.dispatch(command, cwd=base)
            self._write(200, {"ok": True, "capability": result.capability, "summary": result.summary, "command": command})

        def log_message(self, format: str, *args: object) -> None:
            return

    HTTPServer((host, int(port)), Handler).serve_forever()
    return {"ok": True}
