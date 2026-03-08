from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from contextlib import contextmanager
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from uuid import uuid4
import re


def _runtime(base: Path) -> Path:
    p = base / ".zero_os" / "runtime"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _read_json_bytes(handler: BaseHTTPRequestHandler) -> dict:
    try:
        length = int(handler.headers.get("Content-Length", "0"))
    except Exception:
        length = 0
    data = handler.rfile.read(length) if length > 0 else b"{}"
    try:
        payload = json.loads(data.decode("utf-8", errors="replace"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _send_json(handler: BaseHTTPRequestHandler, code: int, payload: dict) -> None:
    body = (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")
    handler.send_response(code)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


@contextmanager
def _connect(path: Path):
    conn = sqlite3.connect(path)
    try:
        yield conn
    finally:
        conn.close()


def _init_db(path: Path) -> None:
    with _connect(path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS chat_messages (
              id TEXT PRIMARY KEY,
              tenant_id TEXT NOT NULL,
              session_id TEXT NOT NULL,
              role TEXT NOT NULL,
              content TEXT NOT NULL,
              created_at REAL NOT NULL
            )
            """
        )
        cols = [str(r[1]) for r in conn.execute("PRAGMA table_info(chat_messages)").fetchall()]
        if "tenant_id" not in cols:
            conn.execute("ALTER TABLE chat_messages ADD COLUMN tenant_id TEXT NOT NULL DEFAULT 'default'")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_chat_session_created ON chat_messages(tenant_id, session_id, created_at)"
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS idempotency_cache (
              key TEXT PRIMARY KEY,
              response_json TEXT NOT NULL,
              created_at REAL NOT NULL
            )
            """
        )
        conn.commit()


def _db_write(path: Path, msg_id: str, tenant_id: str, session_id: str, role: str, content: str) -> None:
    with _connect(path) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO chat_messages(id, tenant_id, session_id, role, content, created_at) VALUES(?,?,?,?,?,?)",
            (msg_id, tenant_id, session_id, role, content, time.time()),
        )
        conn.commit()


def _db_recent(path: Path, tenant_id: str, session_id: str, limit: int = 8) -> list[tuple[str, str]]:
    with _connect(path) as conn:
        rows = conn.execute(
            """
            SELECT role, content
            FROM chat_messages
            WHERE tenant_id=? AND session_id=?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (tenant_id, session_id, max(1, int(limit))),
        ).fetchall()
        rows.reverse()
        return [(str(r[0]), str(r[1])) for r in rows]


def _db_last_by_role(path: Path, tenant_id: str, session_id: str, role: str) -> tuple[str, str] | None:
    with _connect(path) as conn:
        row = conn.execute(
            """
            SELECT id, content
            FROM chat_messages
            WHERE tenant_id=? AND session_id=? AND role=?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (tenant_id, session_id, role),
        ).fetchone()
        if not row:
            return None
        return (str(row[0]), str(row[1]))


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-zA-Z0-9']+", text.lower()))


def _db_ranked_context(path: Path, tenant_id: str, session_id: str, query: str, pool: int = 60, keep: int = 6) -> list[tuple[str, str]]:
    with _connect(path) as conn:
        rows = conn.execute(
            """
            SELECT role, content
            FROM chat_messages
            WHERE tenant_id=? AND session_id=?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (tenant_id, session_id, max(1, int(pool))),
        ).fetchall()
    q = _tokens(query)
    scored: list[tuple[float, str, str]] = []
    for role, content in rows:
        c = str(content)
        t = _tokens(c)
        score = 0.0 if not q else (len(q.intersection(t)) / max(1, len(q)))
        scored.append((score, str(role), c))
    scored.sort(key=lambda x: x[0], reverse=True)
    out = [(r, c) for _, r, c in scored[: max(1, int(keep))]]
    out.reverse()
    return out


def _idempotency_get(path: Path, key: str) -> dict | None:
    if not key:
        return None
    try:
        with _connect(path) as conn:
            row = conn.execute("SELECT response_json FROM idempotency_cache WHERE key=?", (key,)).fetchone()
            if not row:
                return None
            return json.loads(str(row[0]))
    except Exception:
        return None


def _idempotency_set(path: Path, key: str, payload: dict) -> None:
    if not key:
        return
    with _connect(path) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO idempotency_cache(key, response_json, created_at) VALUES(?,?,?)",
            (key, json.dumps(payload, ensure_ascii=False), time.time()),
        )
        conn.commit()


def _check_auth(handler: BaseHTTPRequestHandler) -> bool:
    token = os.getenv("ZERO_OS_API_TOKEN", "").strip()
    if not token:
        return True
    auth = handler.headers.get("Authorization", "")
    if auth == f"Bearer {token}":
        return True
    _send_json(handler, HTTPStatus.UNAUTHORIZED, {"ok": False, "error": {"code": "unauthorized", "message": "unauthorized"}})
    return False


class _RateLimiter:
    def __init__(self, limit_per_minute: int = 60) -> None:
        self.limit = max(1, int(limit_per_minute))
        self.buckets: dict[str, list[float]] = {}

    def allow(self, key: str) -> bool:
        now = time.time()
        bucket = [t for t in self.buckets.get(key, []) if now - t <= 60.0]
        if len(bucket) >= self.limit:
            self.buckets[key] = bucket
            return False
        bucket.append(now)
        self.buckets[key] = bucket
        return True


def run_chat_api(base: Path, host: str = "127.0.0.1", port: int = 8765) -> None:
    runtime = _runtime(base)
    req_path = runtime / "chat_requests.jsonl"
    resp_path = runtime / "chat_responses.jsonl"
    db_path = runtime / "chat_sessions.sqlite"
    req_path.touch(exist_ok=True)
    resp_path.touch(exist_ok=True)
    _init_db(db_path)
    limiter = _RateLimiter(limit_per_minute=int(os.getenv("ZERO_OS_RATE_LIMIT_PER_MIN", "60")))
    timeout_s = float(os.getenv("ZERO_OS_CHAT_WAIT_TIMEOUT_S", "90"))
    stats = {"requests_total": 0, "errors_total": 0, "timeouts_total": 0, "rate_limited_total": 0}
    stats_lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args) -> None:
            return

        def _id(self) -> str:
            auth = self.headers.get("Authorization", "").strip()
            if auth:
                return auth
            return f"ip:{self.client_address[0]}"

        def do_GET(self) -> None:
            if self.path == "/healthz":
                _send_json(self, HTTPStatus.OK, {"ok": True, "service": "zero-os-chat-api"})
                return
            if self.path == "/metrics":
                with stats_lock:
                    payload = {"ok": True, "metrics": dict(stats)}
                _send_json(self, HTTPStatus.OK, payload)
                return
            _send_json(self, HTTPStatus.NOT_FOUND, {"ok": False, "error": "not_found"})

        def do_POST(self) -> None:
            try:
                self._do_post_impl()
            except Exception as exc:
                with stats_lock:
                    stats["errors_total"] += 1
                _send_json(
                    self,
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    {"ok": False, "error": {"code": "internal_error", "message": str(exc)}},
                )

        def _do_post_impl(self) -> None:
            if self.path not in {"/v1/chat/completions", "/v1/chat/stream"}:
                _send_json(self, HTTPStatus.NOT_FOUND, {"ok": False, "error": {"code": "not_found", "message": "not_found"}})
                return
            if not _check_auth(self):
                return
            with stats_lock:
                stats["requests_total"] += 1
            key = self._id()
            if not limiter.allow(key):
                with stats_lock:
                    stats["rate_limited_total"] += 1
                    stats["errors_total"] += 1
                _send_json(
                    self,
                    HTTPStatus.TOO_MANY_REQUESTS,
                    {"ok": False, "error": {"code": "rate_limited", "message": "rate_limited"}},
                )
                return
            payload = _read_json_bytes(self)
            tenant_id = str(payload.get("tenant_id", self.headers.get("X-Tenant-ID", "default"))).strip() or "default"
            session_id = str(payload.get("session_id", "")).strip() or uuid4().hex
            action = str(payload.get("action", "chat")).strip().lower()
            content = str(payload.get("message", "")).strip()
            if action == "regenerate":
                last_user = _db_last_by_role(db_path, tenant_id, session_id, "user")
                if last_user:
                    content = last_user[1]
            elif action == "continue":
                last_assistant = _db_last_by_role(db_path, tenant_id, session_id, "assistant")
                if last_assistant:
                    content = f"Continue this response with consistent style and facts:\n{last_assistant[1]}"
            if not content:
                with stats_lock:
                    stats["errors_total"] += 1
                _send_json(
                    self,
                    HTTPStatus.BAD_REQUEST,
                    {"ok": False, "error": {"code": "invalid_request", "message": "message is required"}},
                )
                return
            idem_key = str(self.headers.get("Idempotency-Key", "")).strip()
            cached = _idempotency_get(db_path, idem_key)
            if cached is not None:
                _send_json(self, HTTPStatus.OK, cached)
                return
            request_id = uuid4().hex
            turn_id = uuid4().hex
            recent = _db_recent(db_path, tenant_id, session_id, limit=4)
            ranked = _db_ranked_context(db_path, tenant_id, session_id, content, pool=60, keep=6)
            context_lines = [f"{r}: {c}" for r, c in recent]
            ranked_lines = [f"{r}: {c}" for r, c in ranked]
            merged = content
            if ranked_lines or context_lines:
                merged = (
                    "Relevant memory:\n"
                    + "\n".join(ranked_lines)
                    + "\nRecent turns:\n"
                    + "\n".join(context_lines)
                    + f"\nUser: {content}"
                )
            user_message_id = uuid4().hex
            _db_write(db_path, user_message_id, tenant_id, session_id, "user", content)
            with req_path.open("a", encoding="utf-8") as handle:
                handle.write(
                    json.dumps(
                        {
                            "request_id": request_id,
                            "tenant_id": tenant_id,
                            "session_id": session_id,
                            "turn_id": turn_id,
                            "action": action,
                            "content": merged,
                            "time_utc": time.time(),
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )

            start = time.time()
            response_payload = None
            offset = 0
            while time.time() - start < timeout_s:
                text = resp_path.read_text(encoding="utf-8", errors="replace")
                lines = text.splitlines()
                if offset > len(lines):
                    offset = 0
                for raw in lines[offset:]:
                    offset += 1
                    try:
                        item = json.loads(raw)
                    except Exception:
                        continue
                    if str(item.get("request_id")) == request_id:
                        response_payload = item
                        break
                if response_payload is not None:
                    break
                time.sleep(0.2)
            if response_payload is None:
                with stats_lock:
                    stats["timeouts_total"] += 1
                    stats["errors_total"] += 1
                _send_json(
                    self,
                    HTTPStatus.GATEWAY_TIMEOUT,
                    {"ok": False, "error": {"code": "daemon_timeout", "message": "timeout_waiting_for_daemon"}},
                )
                return

            answer = str(response_payload.get("output", ""))
            assistant_message_id = uuid4().hex
            _db_write(db_path, assistant_message_id, tenant_id, session_id, "assistant", answer)
            if self.path == "/v1/chat/stream":
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Connection", "keep-alive")
                self.end_headers()
                self.wfile.write(f"data: {json.dumps({'session_id': session_id, 'turn_id': turn_id, 'action': action})}\n\n".encode("utf-8"))
                for token in answer.split():
                    self.wfile.write(f"data: {json.dumps({'delta': token + ' '})}\n\n".encode("utf-8"))
                self.wfile.write(b"data: [DONE]\n\n")
                self.wfile.flush()
                self.close_connection = True
                return

            out = {
                "ok": True,
                "request_id": request_id,
                "tenant_id": tenant_id,
                "session_id": session_id,
                "turn_id": turn_id,
                "action": action,
                "message_id": assistant_message_id,
                "parent_user_message_id": user_message_id,
                "status": response_payload.get("status", "ok"),
                "message": answer,
            }
            _idempotency_set(db_path, idem_key, out)
            _send_json(self, HTTPStatus.OK, out)

    server = ThreadingHTTPServer((host, port), Handler)
    server.serve_forever()
