from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _path(cwd: str) -> Path:
    path = Path(cwd).resolve() / ".zero_os" / "assistant" / "approvals.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(json.dumps({"items": []}, indent=2) + "\n", encoding="utf-8")
    return path


def _load(cwd: str) -> dict:
    return json.loads(_path(cwd).read_text(encoding="utf-8", errors="replace"))


def _save(cwd: str, data: dict) -> None:
    _path(cwd).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def status(cwd: str) -> dict:
    data = _load(cwd)
    return {"ok": True, "count": len(data.get("items", [])), "items": data.get("items", [])[-20:]}


def request_approval(cwd: str, action: str, reason: str, payload: dict | None = None) -> dict:
    data = _load(cwd)
    item = {
        "id": str(uuid.uuid4())[:10],
        "time_utc": _utc_now(),
        "action": action,
        "reason": reason,
        "payload": payload or {},
        "state": "pending",
    }
    data.setdefault("items", []).append(item)
    _save(cwd, data)
    return {"ok": True, "approval": item}


def decide(cwd: str, approval_id: str, approve: bool) -> dict:
    data = _load(cwd)
    for item in data.get("items", []):
        if item.get("id") == approval_id:
            item["state"] = "approved" if approve else "rejected"
            item["decided_utc"] = _utc_now()
            _save(cwd, data)
            return {"ok": True, "approval": item}
    return {"ok": False, "reason": "approval not found"}


def latest_approved(cwd: str, action: str = "") -> dict:
    data = _load(cwd)
    items = list(data.get("items", []))
    for item in reversed(items):
        if item.get("state") != "approved":
            continue
        if action and str(item.get("action", "")) != action:
            continue
        return {"ok": True, "approval": item}
    return {"ok": False, "reason": "no approved item"}
