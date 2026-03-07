from __future__ import annotations

import json
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sys
from urllib.parse import parse_qs, urlparse
import re


BASE = Path(__file__).resolve().parents[1]
RUNTIME = BASE / ".zero_os" / "runtime"
RUNTIME.mkdir(parents=True, exist_ok=True)
SRC = BASE / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from zero_os.highway import Highway


SKIP_PARTS = {".git", ".zero_os", "__pycache__"}
TEXT_SUFFIXES = {".py", ".md", ".txt", ".json", ".yml", ".yaml", ".toml", ".ini", ".cfg", ".ps1", ".html", ".js", ".css"}


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
