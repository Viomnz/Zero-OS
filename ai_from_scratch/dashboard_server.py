from __future__ import annotations

import json
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse


BASE = Path(__file__).resolve().parents[1]
RUNTIME = BASE / ".zero_os" / "runtime"
RUNTIME.mkdir(parents=True, exist_ok=True)


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

