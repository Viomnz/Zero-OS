from __future__ import annotations

import json
from pathlib import Path


def _path(cwd: str) -> Path:
    path = Path(cwd).resolve() / ".zero_os" / "integrations" / "github.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(json.dumps({"repos": {}, "events": []}, indent=2) + "\n", encoding="utf-8")
    return path


def status(cwd: str) -> dict:
    return json.loads(_path(cwd).read_text(encoding="utf-8", errors="replace"))


def connect_repo(cwd: str, repo: str, token: str = "") -> dict:
    data = status(cwd)
    data.setdefault("repos", {})[repo] = {"token_set": bool(token), "connected": True}
    _path(cwd).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return {"ok": True, "repo": repo}


def issue_summary(cwd: str, repo: str) -> dict:
    return {"ok": True, "repo": repo, "issues": [{"id": 1, "title": "sample issue", "state": "open"}]}
