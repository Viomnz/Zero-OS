from __future__ import annotations

import json
from pathlib import Path


def _path(cwd: str) -> Path:
    path = Path(cwd).resolve() / ".zero_os" / "assistant" / "playbooks.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(json.dumps({"playbooks": {}}, indent=2) + "\n", encoding="utf-8")
    return path


def _load(cwd: str) -> dict:
    return json.loads(_path(cwd).read_text(encoding="utf-8", errors="replace"))


def _save(cwd: str, data: dict) -> None:
    _path(cwd).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def status(cwd: str) -> dict:
    data = _load(cwd)
    return {"ok": True, "count": len(data.get("playbooks", {})), "playbooks": data.get("playbooks", {})}


def remember(cwd: str, key: str, plan: dict) -> dict:
    data = _load(cwd)
    data.setdefault("playbooks", {})[key] = plan
    _save(cwd, data)
    return {"ok": True, "key": key, "plan": plan}


def lookup(cwd: str, key: str) -> dict:
    data = _load(cwd)
    plan = data.get("playbooks", {}).get(key)
    if not plan:
        return {"ok": False, "reason": "playbook not found"}
    return {"ok": True, "key": key, "plan": plan}
