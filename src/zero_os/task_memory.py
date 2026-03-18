from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _path(cwd: str) -> Path:
    path = Path(cwd).resolve() / ".zero_os" / "assistant" / "task_memory.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(json.dumps({"tasks": []}, indent=2) + "\n", encoding="utf-8")
    return path


def load_memory(cwd: str) -> dict:
    return json.loads(_path(cwd).read_text(encoding="utf-8", errors="replace"))


def save_task_run(cwd: str, request: str, run: dict) -> dict:
    data = load_memory(cwd)
    results = list(run.get("results", []))
    total_steps = len(run.get("plan", {}).get("steps", []))
    completed_steps = 0
    for item in results:
        if not item.get("ok", False):
            break
        completed_steps += 1
    rec = {
        "time_utc": _utc_now(),
        "run_id": str(run.get("run_id", "")).strip(),
        "request": request,
        "ok": bool(run.get("ok", False)),
        "plan": run.get("plan", {}),
        "results": results,
        "completed_steps": completed_steps,
        "total_steps": total_steps,
        "resume_from": completed_steps if completed_steps < total_steps else total_steps,
        "response": run.get("response", {}),
    }
    data.setdefault("tasks", []).append(rec)
    data["tasks"] = data["tasks"][-100:]
    _path(cwd).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return rec


def status(cwd: str) -> dict:
    data = load_memory(cwd)
    tasks = data.get("tasks", [])
    return {
        "ok": True,
        "count": len(tasks),
        "last": tasks[-1] if tasks else {},
    }


def latest_resumable(cwd: str) -> dict:
    data = load_memory(cwd)
    tasks = list(data.get("tasks", []))
    for task in reversed(tasks):
        if int(task.get("resume_from", 0)) < int(task.get("total_steps", 0)):
            return {"ok": True, "task": task}
    return {"ok": False, "reason": "no resumable task"}
