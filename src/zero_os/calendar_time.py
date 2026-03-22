from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _assistant_dir(cwd: str) -> Path:
    path = Path(cwd).resolve() / ".zero_os" / "assistant"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _path(cwd: str) -> Path:
    return _assistant_dir(cwd) / "calendar_time.json"


def _load(path: Path, default: dict) -> dict:
    if not path.exists():
        return dict(default)
    try:
        raw = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return dict(default)
    if not isinstance(raw, dict):
        return dict(default)
    merged = dict(default)
    merged.update(raw)
    return merged


def _save(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _default_state() -> dict:
    return {
        "schema_version": 1,
        "enabled": True,
        "last_refreshed_utc": "",
        "reminders": [],
        "calendar_items": [],
        "audit": [],
    }


def _state(cwd: str) -> dict:
    return _load(_path(cwd), _default_state())


def _summarize(state: dict, cwd: str) -> dict:
    state["ok"] = True
    state["path"] = str(_path(cwd))
    state["summary"] = {
        "enabled": bool(state.get("enabled", True)),
        "reminder_count": len(list(state.get("reminders", []))),
        "calendar_item_count": len(list(state.get("calendar_items", []))),
        "audit_count": len(list(state.get("audit", []))),
    }
    return state


def calendar_time_status(cwd: str) -> dict:
    state = _summarize(_state(cwd), cwd)
    _save(_path(cwd), state)
    return state


def calendar_time_refresh(cwd: str) -> dict:
    state = _state(cwd)
    state["last_refreshed_utc"] = _utc_now()
    state.setdefault("audit", []).append({"time_utc": _utc_now(), "action": "refresh"})
    state = _summarize(state, cwd)
    _save(_path(cwd), state)
    return state


def calendar_reminder_add(cwd: str, title: str, when: str) -> dict:
    state = _state(cwd)
    reminder = {
        "id": f"reminder_{len(list(state.get('reminders', []))) + 1}",
        "time_utc": _utc_now(),
        "title": title.strip(),
        "when": when.strip(),
        "status": "scheduled",
    }
    state.setdefault("reminders", []).append(reminder)
    state.setdefault("audit", []).append(
        {
            "time_utc": reminder["time_utc"],
            "action": "reminder_add",
            "title": reminder["title"],
            "when": reminder["when"],
        }
    )
    state = _summarize(state, cwd)
    _save(_path(cwd), state)
    return {"ok": True, "reminder": reminder, "summary": state["summary"], "path": state["path"]}


def calendar_reminder_tick(cwd: str, now_iso: str = "") -> dict:
    state = _state(cwd)
    now = datetime.fromisoformat(now_iso) if now_iso else datetime.now(timezone.utc)
    reminders = list(state.get("reminders", []))
    fired: list[dict] = []
    remaining: list[dict] = []
    for reminder in reminders:
        when_raw = str(reminder.get("when", "")).strip()
        try:
            when = datetime.fromisoformat(when_raw)
        except ValueError:
            remaining.append(reminder)
            continue
        if str(reminder.get("status", "")) == "scheduled" and when <= now:
            updated = dict(reminder)
            updated["status"] = "executed"
            updated["executed_utc"] = now.isoformat()
            fired.append(updated)
            state.setdefault("audit", []).append(
                {
                    "time_utc": now.isoformat(),
                    "action": "reminder_executed",
                    "reminder_id": updated["id"],
                    "title": updated["title"],
                }
            )
            continue
        remaining.append(reminder)
    state["reminders"] = remaining
    state.setdefault("calendar_items", []).extend(fired)
    state = _summarize(state, cwd)
    _save(_path(cwd), state)
    return {
        "ok": True,
        "executed_count": len(fired),
        "executed": fired,
        "summary": state["summary"],
        "path": state["path"],
    }
