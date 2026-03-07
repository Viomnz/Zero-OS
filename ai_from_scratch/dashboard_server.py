from __future__ import annotations

import json
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sys
from urllib.parse import parse_qs, urlparse
import re
import sqlite3
import time
from uuid import uuid4


BASE = Path(__file__).resolve().parents[1]
RUNTIME = BASE / ".zero_os" / "runtime"
RUNTIME.mkdir(parents=True, exist_ok=True)
SRC = BASE / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from zero_os.highway import Highway


SKIP_PARTS = {".git", ".zero_os", "__pycache__"}
TEXT_SUFFIXES = {".py", ".md", ".txt", ".json", ".yml", ".yaml", ".toml", ".ini", ".cfg", ".ps1", ".html", ".js", ".css"}


def _chat_db_path() -> Path:
    return RUNTIME / "chat_sessions.sqlite"


def _init_chat_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    try:
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
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_chat_session_created ON chat_messages(tenant_id, session_id, created_at)"
        )
        conn.commit()
    finally:
        conn.close()


def _db_write(path: Path, msg_id: str, tenant_id: str, session_id: str, role: str, content: str) -> None:
    conn = sqlite3.connect(path)
    try:
        conn.execute(
            "INSERT OR REPLACE INTO chat_messages(id, tenant_id, session_id, role, content, created_at) VALUES(?,?,?,?,?,?)",
            (msg_id, tenant_id, session_id, role, content, time.time()),
        )
        conn.commit()
    finally:
        conn.close()


def _db_recent(path: Path, tenant_id: str, session_id: str, limit: int = 4) -> list[tuple[str, str]]:
    conn = sqlite3.connect(path)
    try:
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
    finally:
        conn.close()


def _db_last_by_role(path: Path, tenant_id: str, session_id: str, role: str) -> tuple[str, str] | None:
    conn = sqlite3.connect(path)
    try:
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
    finally:
        conn.close()


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-zA-Z0-9']+", text.lower()))


def _db_ranked_context(path: Path, tenant_id: str, session_id: str, query: str, pool: int = 60, keep: int = 6) -> list[tuple[str, str]]:
    conn = sqlite3.connect(path)
    try:
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
    finally:
        conn.close()
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


def _tokenize(text: str) -> list[str]:
    return [t for t in re.split(r"[^a-z0-9_./-]+", text.lower()) if t]


def _logical_suggestions(path: Path, preview: str) -> list[str]:
    p = str(path).replace("\\", "/").lower()
    out: list[str] = []
    if p.endswith((".yml", ".yaml")) and ".github/workflows/" in p:
        out.append("CI flow found: validate job dependencies and required security gates.")
    if p.endswith(".py") and "test" in p:
        out.append("Test file matched: add failing-case coverage before feature expansion.")
    if p.endswith(".py") and ("antivirus" in p or "firewall" in p or "security" in p):
        out.append("Security module matched: keep strict defaults and verify score/root_issues output.")
    if "todo" in preview.lower():
        out.append("TODO marker found: convert TODOs into tracked issues with acceptance checks.")
    if "fixme" in preview.lower():
        out.append("FIXME marker found: prioritize patch or isolate risky behavior.")
    if "password" in preview.lower() or "token" in preview.lower():
        out.append("Credential-like text matched: verify secrets are not hardcoded.")
    if not out:
        out.append("Direct match found: review nearby logic and update tests for this path.")
    return out


def _security_focus(path_text: str, tokens: list[str]) -> int:
    p = path_text.lower()
    token_set = set(tokens)
    wants_security = bool(token_set.intersection({"cure", "curefirewall", "firewall", "antivirus", "security", "virus"}))
    is_cure = ("cure_firewall" in p) or ("cure-firewall" in p) or ("firewall" in p)
    is_av = "antivirus" in p
    is_sec = "security" in p
    if not wants_security:
        return 0
    score = 0
    if is_cure:
        score += 3
    if is_av:
        score += 3
    if is_sec:
        score += 1
    return score


def smart_find(base: Path, query: str, max_results: int = 25) -> dict:
    tokens = _tokenize(query)
    if not tokens:
        return {"ok": False, "reason": "query required"}
    results = []
    cap = max(1, min(120, int(max_results)))
    for p in base.rglob("*"):
        if not p.is_file():
            continue
        if any(part in SKIP_PARTS for part in p.parts):
            continue
        rel = str(p.relative_to(base)).replace("\\", "/")
        name_l = p.name.lower()
        text = ""
        if p.suffix.lower() in TEXT_SUFFIXES:
            try:
                text = p.read_text(encoding="utf-8", errors="replace")
            except Exception:
                text = ""
        haystack = f"{rel.lower()}\n{text.lower()}"
        hit_tokens = [t for t in tokens if t in haystack]
        if not hit_tokens:
            continue
        score = round((len(hit_tokens) / len(tokens)) * 100, 2)
        security_focus = _security_focus(rel, tokens)
        idx = max((haystack.find(t) for t in hit_tokens), default=-1)
        preview = text[max(0, idx - 80): idx + 180].replace("\n", " ").strip() if text and idx >= 0 else ""
        results.append(
            {
                "path": rel,
                "token_match_count": len(hit_tokens),
                "token_match_ratio": score,
                "matched_tokens": hit_tokens,
                "preview": preview[:240],
                "suggestions": _logical_suggestions(p, preview),
                "security_focus": security_focus,
            }
        )
    results.sort(
        key=lambda x: (
            x.get("security_focus", 0),
            x["token_match_count"],
            x["token_match_ratio"],
        ),
        reverse=True,
    )
    top = results[:cap]
    return {
        "ok": True,
        "query": query,
        "token_count": len(tokens),
        "result_count": len(top),
        "results": top,
        "logic_mode": "pure",
    }


class Handler(SimpleHTTPRequestHandler):
    def translate_path(self, path: str) -> str:
        root = str(BASE)
        path = path.split("?", 1)[0].split("#", 1)[0]
        full = (BASE / path.lstrip("/")).resolve()
        try:
            full.relative_to(BASE)
        except ValueError:
            return root
        return str(full)

    def do_POST(self) -> None:
        if self.path == "/api/chat":
            payload = self._payload_or_400()
            if payload is None:
                return
            tenant_id = str(payload.get("tenant_id", "default")).strip() or "default"
            session_id = str(payload.get("session_id", "")).strip() or uuid4().hex
            action = str(payload.get("action", "chat")).strip().lower()
            message = str(payload.get("message", "")).strip()
            db_path = _chat_db_path()
            _init_chat_db(db_path)
            if action == "regenerate":
                last_user = _db_last_by_role(db_path, tenant_id, session_id, "user")
                if last_user:
                    message = last_user[1]
            elif action == "continue":
                last_assistant = _db_last_by_role(db_path, tenant_id, session_id, "assistant")
                if last_assistant:
                    message = f"Continue this response with consistent style and facts:\n{last_assistant[1]}"
            if not message:
                self.send_error(400, "Message required")
                return
            request_id = uuid4().hex
            turn_id = uuid4().hex
            user_message_id = uuid4().hex
            recent = _db_recent(db_path, tenant_id, session_id, limit=4)
            ranked = _db_ranked_context(db_path, tenant_id, session_id, message, pool=60, keep=6)
            context_lines = [f"{r}: {c}" for r, c in recent]
            ranked_lines = [f"{r}: {c}" for r, c in ranked]
            merged = (
                "Relevant memory:\n"
                + "\n".join(ranked_lines)
                + "\nRecent turns:\n"
                + "\n".join(context_lines)
                + f"\nUser: {message}"
            )
            _db_write(db_path, user_message_id, tenant_id, session_id, "user", message)
            req_path = RUNTIME / "chat_requests.jsonl"
            req_path.touch(exist_ok=True)
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
            resp_path = RUNTIME / "chat_responses.jsonl"
            resp_path.touch(exist_ok=True)
            timeout_s = 90.0
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
                self.send_error(504, "timeout_waiting_for_daemon")
                return
            answer = str(response_payload.get("output", ""))
            assistant_message_id = uuid4().hex
            _db_write(db_path, assistant_message_id, tenant_id, session_id, "assistant", answer)
            self._json(
                {
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
            )
            return
        if self.path == "/api/smart-find":
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length).decode("utf-8", errors="replace")
            try:
                payload = json.loads(body)
            except json.JSONDecodeError:
                self.send_error(400, "Invalid JSON")
                return
            query = str(payload.get("query", "")).strip()
            max_results = int(payload.get("max_results", 25))
            out = smart_find(BASE, query, max_results=max_results)
            if not out.get("ok", False):
                self.send_error(400, out.get("reason", "invalid request"))
                return
            self._json(out)
            return
        if self.path == "/api/exec":
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length).decode("utf-8", errors="replace")
            try:
                payload = json.loads(body)
            except json.JSONDecodeError:
                self.send_error(400, "Invalid JSON")
                return
            command = str(payload.get("command", "")).strip()
            if not command:
                self.send_error(400, "Command required")
                return
            # Route through unified shell lane by default.
            task = command if command.lower().startswith(("shell run ", "terminal run ", "powershell run ")) else f"shell run {command}"
            result = Highway(cwd=str(BASE)).dispatch(task, cwd=str(BASE))
            self._json({"ok": True, "task": task, "lane": result.capability, "output": result.summary})
            return
        if self.path != "/api/task":
            self.send_error(404, "Not found")
            return
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length).decode("utf-8", errors="replace")
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            self.send_error(400, "Invalid JSON")
            return
        prompt = str(payload.get("prompt", "")).strip()
        if not prompt:
            self.send_error(400, "Prompt required")
            return
        inbox = RUNTIME / "zero_ai_tasks.txt"
        with inbox.open("a", encoding="utf-8") as handle:
            handle.write(prompt + "\n")
            self._json({"queued": True, "prompt": prompt})

    def _payload_or_400(self) -> dict | None:
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length).decode("utf-8", errors="replace")
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            self.send_error(400, "Invalid JSON")
            return None

    def do_GET(self) -> None:
        if self.path.startswith("/api/output"):
            qs = parse_qs(urlparse(self.path).query)
            tail = int(qs.get("tail", ["60"])[0])
            out = RUNTIME / "zero_ai_output.txt"
            if out.exists():
                lines = out.read_text(encoding="utf-8", errors="replace").splitlines()
                text = "\n".join(lines[-max(1, min(400, tail)):])
            else:
                text = ""
            self._json({"text": text})
            return
        super().do_GET()

    def _json(self, payload: dict) -> None:
        raw = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


def main() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 8765), Handler)
    print("dashboard server on http://127.0.0.1:8765")
    server.serve_forever()


if __name__ == "__main__":
    main()
