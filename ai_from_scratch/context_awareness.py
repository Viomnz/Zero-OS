from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


def _runtime(cwd: str) -> Path:
    p = Path(cwd).resolve() / ".zero_os" / "runtime"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_tail_lines(path: Path, limit: int = 80) -> list[str]:
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    return lines[-max(1, limit):]


def detect_context(cwd: str, prompt: str, channel: str) -> dict:
    rt = _runtime(cwd)
    heartbeat = rt / "zero_ai_heartbeat.json"
    output = rt / "zero_ai_output.txt"
    tasks = rt / "zero_ai_tasks.txt"

    system_state = {"daemon_running": False, "checkpoint_loaded": False}
    if heartbeat.exists():
        try:
            hb = json.loads(heartbeat.read_text(encoding="utf-8", errors="replace"))
            system_state["daemon_running"] = str(hb.get("status", "")) == "running"
            system_state["checkpoint_loaded"] = bool(hb.get("checkpoint_loaded", False))
        except Exception:
            pass

    history_tail = _read_tail_lines(output, limit=120)
    recent_rejections = sum(1 for ln in history_tail if "REJECTED_" in ln or "ENTERED_SAFE_STATE" in ln)
    recent_safe_state = any("ENTERED_SAFE_STATE" in ln for ln in history_tail)
    emergency = recent_safe_state or recent_rejections >= 4

    task_obj = {
        "prompt": str(prompt or "").strip(),
        "objective": "safety_priority" if emergency else "normal_operation",
        "channel": channel,
    }

    user_interaction = {
        "queue_depth": len(_read_tail_lines(tasks, limit=500)),
        "recent_rejections": recent_rejections,
    }

    context = {
        "time_utc": _utc_now(),
        "environment": system_state,
        "task": task_obj,
        "history": {"recent_safe_state": recent_safe_state, "recent_rejections": recent_rejections},
        "user_interaction": user_interaction,
        "context_changed": emergency,
    }
    params = {
        "priority_mode": "safety" if emergency else "normal",
        "max_candidates": 6 if emergency else 9,
        "force_profile": "adaptive" if emergency else None,
        "force_mode": "stability" if emergency else None,
    }
    out = {"ok": True, "context": context, "reasoning_parameters": params}
    (rt / "context_awareness.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    return out

