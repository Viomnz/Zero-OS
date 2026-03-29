from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_utc(value: str) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _assistant_dir(cwd: str) -> Path:
    path = Path(cwd).resolve() / ".zero_os" / "assistant"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _goals_path(cwd: str) -> Path:
    return _assistant_dir(cwd) / "goals.json"


def _loop_path(cwd: str) -> Path:
    return _assistant_dir(cwd) / "autonomy_loop_state.json"


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return default


def goal_memory_status(cwd: str) -> dict[str, Any]:
    goals_state = dict(_load_json(_goals_path(cwd), {"goals": [], "current_goal_id": ""}) or {})
    loop_state = dict(_load_json(_loop_path(cwd), {"enabled": False, "next_run_utc": ""}) or {})
    goals = [dict(item or {}) for item in list(goals_state.get("goals", [])) if isinstance(item, dict)]
    current_goal_id = str(goals_state.get("current_goal_id", "") or "")
    current_goal = next((goal for goal in goals if str(goal.get("id", "")) == current_goal_id), None)
    if current_goal is None:
        current_goal = next((goal for goal in goals if str(goal.get("state", "")) in {"open", "blocked"}), None)

    open_goals = [goal for goal in goals if str(goal.get("state", "")) == "open"]
    blocked_goals = [goal for goal in goals if str(goal.get("state", "")) == "blocked"]
    resolved_goals = [goal for goal in goals if str(goal.get("state", "")) == "resolved"]
    next_run = _parse_utc(str(loop_state.get("next_run_utc", "")))
    loop_due_now = bool(loop_state.get("enabled", False)) and (next_run is None or datetime.now(timezone.utc) >= next_run)

    return {
        "ok": True,
        "time_utc": _utc_now(),
        "goals_path": str(_goals_path(cwd)),
        "loop_path": str(_loop_path(cwd)),
        "goal_count": len(goals),
        "open_count": len(open_goals),
        "blocked_count": len(blocked_goals),
        "resolved_count": len(resolved_goals),
        "current_goal": dict(current_goal or {}),
        "current_goal_title": str((current_goal or {}).get("title", "")),
        "current_goal_next_action": str((current_goal or {}).get("next_action", "")),
        "current_goal_requires_user": bool((current_goal or {}).get("requires_user", False)),
        "current_goal_state": str((current_goal or {}).get("state", "")),
        "current_goal_risk": str((current_goal or {}).get("risk", "low") or "low"),
        "current_goal_blocked_reason": str((current_goal or {}).get("blocked_reason", "")),
        "current_goal_action_kind": str((current_goal or {}).get("action_kind", "") or ""),
        "loop_enabled": bool(loop_state.get("enabled", False)),
        "loop_due_now": loop_due_now,
        "loop_interval_seconds": int(loop_state.get("interval_seconds", 0) or 0),
    }
