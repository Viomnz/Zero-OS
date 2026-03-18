from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


_DEFAULT_EXPIRY_HOURS = 24
_SHORT_EXPIRY_HOURS = 6


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


def _parse_utc(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _expiry_hours(action: str) -> int:
    kind = str(action or "").strip().lower()
    if kind == "browser_action":
        return _SHORT_EXPIRY_HOURS
    return _DEFAULT_EXPIRY_HOURS


def _default_expiry_utc(action: str, created_utc: str) -> str:
    created = _parse_utc(created_utc) or datetime.now(timezone.utc)
    return (created + timedelta(hours=_expiry_hours(action))).isoformat()


def _sweep_expired_items(data: dict) -> int:
    changed = 0
    now = datetime.now(timezone.utc)
    for item in data.get("items", []):
        state = str(item.get("state", "")).strip()
        if state not in {"pending", "approved"}:
            continue
        created_utc = str(item.get("time_utc", "")).strip() or _utc_now()
        item.setdefault("expires_utc", _default_expiry_utc(str(item.get("action", "")), created_utc))
        expires_at = _parse_utc(str(item.get("expires_utc", "")))
        if expires_at is None or now < expires_at:
            continue
        item["state"] = "expired"
        item["expired_utc"] = now.isoformat()
        item["expiration_reason"] = "approval_window_closed"
        changed += 1
    return changed


def _load_and_sweep(cwd: str) -> tuple[dict, int]:
    data = _load(cwd)
    changed = _sweep_expired_items(data)
    if changed:
        _save(cwd, data)
    return data, changed


def status(cwd: str) -> dict:
    data, expired_count = _load_and_sweep(cwd)
    items = list(data.get("items", []))
    counts_by_state: dict[str, int] = {}
    actionable_pending_count = 0
    for item in items:
        state = str(item.get("state", "")).strip() or "unknown"
        counts_by_state[state] = counts_by_state.get(state, 0) + 1
        if state == "pending":
            actionable_pending_count += 1
    return {
        "ok": True,
        "count": len(items),
        "pending_count": actionable_pending_count,
        "expired_count": int(counts_by_state.get("expired", 0)),
        "expired_in_last_sweep": expired_count,
        "counts_by_state": counts_by_state,
        "items": items[-20:],
    }


def _target_signature(target: Any) -> str:
    if target is None:
        return ""
    return json.dumps(target, sort_keys=True, default=str)


def _item_run_id(item: dict) -> str:
    payload = dict(item.get("payload") or {})
    return str(item.get("run_id", "") or payload.get("run_id", "")).strip()


def _item_target_signature(item: dict) -> str:
    payload = dict(item.get("payload") or {})
    explicit = str(item.get("target_signature", "")).strip()
    if explicit:
        return explicit
    return _target_signature(payload.get("target"))


def _matches(item: dict, *, action: str = "", run_id: str = "", target: Any = None, states: tuple[str, ...] = ()) -> bool:
    if states and str(item.get("state", "")) not in set(states):
        return False
    if action and str(item.get("action", "")).strip() != str(action).strip():
        return False
    if run_id and _item_run_id(item) != str(run_id).strip():
        return False
    if target is not None and _item_target_signature(item) != _target_signature(target):
        return False
    return True


def request_approval(cwd: str, action: str, reason: str, payload: dict | None = None) -> dict:
    data, _ = _load_and_sweep(cwd)
    safe_payload = dict(payload or {})
    created_utc = _utc_now()
    item = {
        "id": str(uuid.uuid4())[:10],
        "time_utc": created_utc,
        "action": action,
        "reason": reason,
        "payload": safe_payload,
        "run_id": str(safe_payload.get("run_id", "")).strip(),
        "target_signature": _target_signature(safe_payload.get("target")),
        "expires_utc": _default_expiry_utc(action, created_utc),
        "state": "pending",
    }
    data.setdefault("items", []).append(item)
    _save(cwd, data)
    return {"ok": True, "approval": item}


def decide(cwd: str, approval_id: str, approve: bool) -> dict:
    data, _ = _load_and_sweep(cwd)
    for item in data.get("items", []):
        if item.get("id") == approval_id:
            if str(item.get("state", "")) != "pending":
                return {"ok": False, "reason": "approval already decided", "approval": item}
            item["state"] = "approved" if approve else "rejected"
            item["decided_utc"] = _utc_now()
            _save(cwd, data)
            return {"ok": True, "approval": item}
    return {"ok": False, "reason": "approval not found"}


def latest_pending(cwd: str, action: str = "", *, run_id: str = "", target: Any = None) -> dict:
    data, _ = _load_and_sweep(cwd)
    items = list(data.get("items", []))
    for item in reversed(items):
        if _matches(item, action=action, run_id=run_id, target=target, states=("pending",)):
            return {"ok": True, "approval": item}
    return {"ok": False, "reason": "no pending item"}


def latest_approved(cwd: str, action: str = "", *, run_id: str = "", target: Any = None) -> dict:
    data, _ = _load_and_sweep(cwd)
    items = list(data.get("items", []))
    for item in reversed(items):
        if _matches(item, action=action, run_id=run_id, target=target, states=("approved",)):
            return {"ok": True, "approval": item}
    return {"ok": False, "reason": "no approved item"}


def mark_executed(cwd: str, approval_id: str, *, outcome: str = "") -> dict:
    data, _ = _load_and_sweep(cwd)
    for item in data.get("items", []):
        if str(item.get("id", "")) != str(approval_id):
            continue
        if str(item.get("state", "")) != "approved":
            return {"ok": False, "reason": "approval not executable", "approval": item}
        item["state"] = "executed"
        item["executed_utc"] = _utc_now()
        if outcome:
            item["execution_outcome"] = str(outcome)
        _save(cwd, data)
        return {"ok": True, "approval": item}
    return {"ok": False, "reason": "approval not found"}


def cleanup_expired(cwd: str) -> dict:
    data, changed = _load_and_sweep(cwd)
    return {
        "ok": True,
        "expired_count": changed,
        "status": status(cwd),
        "items": data.get("items", [])[-20:],
    }
