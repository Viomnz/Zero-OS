from __future__ import annotations

from contextlib import contextmanager
import json
import secrets
import sqlite3
import shutil
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse

from zero_os.production_core import sync_path_smart


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _db_path(cwd: str) -> Path:
    path = Path(cwd).resolve() / ".zero_os" / "native_store" / "backend.db"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _connect(cwd: str) -> sqlite3.Connection:
    conn = sqlite3.connect(_db_path(cwd))
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def _connection(cwd: str):
    conn = _connect(cwd)
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def _deploy_root(cwd: str) -> Path:
    root = Path(cwd).resolve() / "build" / "native_store_prod" / "backend_deploy"
    root.mkdir(parents=True, exist_ok=True)
    return root


def init_db(cwd: str) -> dict:
    with _connection(cwd) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                applied_utc TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                email TEXT NOT NULL,
                tier TEXT NOT NULL,
                created_utc TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS charges (
                charge_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                amount REAL NOT NULL,
                currency TEXT NOT NULL,
                created_utc TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS events (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                kind TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_utc TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS api_tokens (
                token_id TEXT PRIMARY KEY,
                token_secret TEXT NOT NULL,
                scope TEXT NOT NULL,
                created_utc TEXT NOT NULL,
                active INTEGER NOT NULL
            );
            """
        )
        conn.execute(
            "INSERT OR IGNORE INTO schema_migrations(version, applied_utc) VALUES (?, ?)",
            (1, _utc_now()),
        )
    return {"ok": True, "db": str(_db_path(cwd))}


def create_user(cwd: str, user_id: str, email: str, tier: str) -> dict:
    init_db(cwd)
    with _connection(cwd) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO users(user_id, email, tier, created_utc) VALUES (?, ?, ?, ?)",
            (user_id, email, tier, _utc_now()),
        )
    return {"ok": True, "user_id": user_id}


def issue_token(cwd: str, token_id: str, scope: str) -> dict:
    init_db(cwd)
    secret = secrets.token_hex(16)
    with _connection(cwd) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO api_tokens(token_id, token_secret, scope, created_utc, active) VALUES (?, ?, ?, ?, ?)",
            (token_id, secret, scope, _utc_now(), 1),
        )
    return {"ok": True, "token_id": token_id, "token_secret": secret, "scope": scope}


def validate_token(cwd: str, token_secret: str, scope: str = "") -> bool:
    init_db(cwd)
    with _connection(cwd) as conn:
        row = conn.execute(
            "SELECT scope, active FROM api_tokens WHERE token_secret = ?",
            (token_secret,),
        ).fetchone()
    if not row or int(row["active"]) != 1:
        return False
    return not scope or str(row["scope"]) == scope


def charge_user(cwd: str, charge_id: str, user_id: str, amount: float, currency: str) -> dict:
    init_db(cwd)
    with _connection(cwd) as conn:
        conn.execute(
            "INSERT INTO charges(charge_id, user_id, amount, currency, created_utc) VALUES (?, ?, ?, ?, ?)",
            (charge_id, user_id, float(amount), currency.upper(), _utc_now()),
        )
    return {"ok": True, "charge_id": charge_id}


def record_event(cwd: str, kind: str, payload: dict) -> dict:
    init_db(cwd)
    with _connection(cwd) as conn:
        conn.execute(
            "INSERT INTO events(kind, payload_json, created_utc) VALUES (?, ?, ?)",
            (kind, json.dumps(payload, sort_keys=True), _utc_now()),
        )
    return {"ok": True, "kind": kind}


def status(cwd: str) -> dict:
    init_db(cwd)
    with _connection(cwd) as conn:
        users = conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]
        charges = conn.execute("SELECT COUNT(*) AS c FROM charges").fetchone()["c"]
        events = conn.execute("SELECT COUNT(*) AS c FROM events").fetchone()["c"]
        migrations = [row["version"] for row in conn.execute("SELECT version FROM schema_migrations ORDER BY version").fetchall()]
        tokens = conn.execute("SELECT COUNT(*) AS c FROM api_tokens WHERE active = 1").fetchone()["c"]
    return {"ok": True, "db": str(_db_path(cwd)), "users": users, "charges": charges, "events": events, "active_tokens": tokens, "migrations": migrations}


def scaffold_deploy(cwd: str) -> dict:
    root = _deploy_root(cwd)
    files = {
        root / "Dockerfile": """FROM python:3.12-slim
WORKDIR /app
COPY src /app/src
ENV PYTHONPATH=/app/src
CMD ["python", "-c", "from zero_os.native_store_backend import run_server; run_server('/app')"]
""",
        root / "docker-compose.yml": """version: "3.9"
services:
  zero-store-backend:
    build:
      context: ../..
      dockerfile: build/native_store_prod/backend_deploy/Dockerfile
    ports:
      - "8088:8088"
    volumes:
      - ../../.zero_os/native_store:/app/.zero_os/native_store
""",
        root / "zero-store-backend.service": """[Unit]
Description=Zero Store Backend
After=network.target

[Service]
WorkingDirectory=/opt/zero-store
ExecStart=/usr/bin/python3 -c 'from zero_os.native_store_backend import run_server; run_server(\"/opt/zero-store\")'
Restart=always

[Install]
WantedBy=multi-user.target
""",
    }
    created = []
    for path, content in files.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            tmp = path.with_suffix(path.suffix + ".incoming")
            tmp.write_text(content, encoding="utf-8")
            sync_path_smart(cwd, str(tmp), str(path))
            tmp.unlink(missing_ok=True)
        else:
            path.write_text(content, encoding="utf-8")
        created.append(str(path))
    return {"ok": True, "created": created, "root": str(root)}


def backup_db(cwd: str, name: str = "") -> dict:
    init_db(cwd)
    backup_dir = Path(cwd).resolve() / ".zero_os" / "native_store" / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    target = backup_dir / f"{name or 'backend'}_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}.db"
    shutil.copy2(_db_path(cwd), target)
    return {"ok": True, "backup": str(target)}


def restore_db(cwd: str, path: str) -> dict:
    src = Path(path).resolve()
    if not src.exists():
        return {"ok": False, "reason": "backup not found"}
    sync = sync_path_smart(cwd, str(src), str(_db_path(cwd)))
    return {"ok": bool(sync.get("ok", False)), "restored_from": str(src), "db": str(_db_path(cwd)), "sync": sync}


def run_server(cwd: str, host: str = "127.0.0.1", port: int = 8088) -> dict:
    init_db(cwd)
    base = cwd

    class Handler(BaseHTTPRequestHandler):
        def _auth(self, scope: str = "") -> bool:
            token = self.headers.get("Authorization", "").removeprefix("Bearer ").strip()
            return validate_token(base, token, scope)

        def _write(self, code: int, payload: dict) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path == "/health":
                self._write(200, status(base))
                return
            if parsed.path == "/events":
                if not self._auth("events:read"):
                    self._write(401, {"ok": False, "reason": "unauthorized"})
                    return
                with _connection(base) as conn:
                    rows = conn.execute("SELECT kind, payload_json, created_utc FROM events ORDER BY event_id DESC LIMIT 25").fetchall()
                self._write(
                    200,
                    {
                        "ok": True,
                        "events": [{"kind": row["kind"], "payload": json.loads(row["payload_json"]), "created_utc": row["created_utc"]} for row in rows],
                    },
                )
                return
            self._write(404, {"ok": False, "reason": "not found"})

        def do_POST(self) -> None:
            parsed = urlparse(self.path)
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length) if length > 0 else b"{}"
            payload = json.loads(raw.decode("utf-8"))
            if parsed.path == "/identity/login":
                self._write(200, create_user(base, payload["user_id"], payload["email"], payload.get("tier", "free")))
                return
            if parsed.path == "/identity/token":
                self._write(200, issue_token(base, payload["token_id"], payload.get("scope", "events:read")))
                return
            if parsed.path == "/payments/charge":
                if not self._auth("payments:write"):
                    self._write(401, {"ok": False, "reason": "unauthorized"})
                    return
                self._write(200, charge_user(base, payload["charge_id"], payload["user_id"], payload["amount"], payload.get("currency", "USD")))
                return
            if parsed.path == "/events":
                if not self._auth("events:write"):
                    self._write(401, {"ok": False, "reason": "unauthorized"})
                    return
                self._write(200, record_event(base, payload["kind"], payload.get("payload", {})))
                return
            self._write(404, {"ok": False, "reason": "not found"})

        def log_message(self, format: str, *args: object) -> None:
            return

    HTTPServer((host, int(port)), Handler).serve_forever()
    return {"ok": True}
