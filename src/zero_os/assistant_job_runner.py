from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from zero_os.self_continuity import (
    zero_ai_continuity_governance_auto_status,
    zero_ai_continuity_governance_set,
    zero_ai_continuity_governance_status,
    zero_ai_continuity_governance_tick,
)
from zero_os.calendar_time import calendar_reminder_tick
from zero_os.communications import communications_tick
from zero_os.task_executor import run_task, run_task_resume


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _path(cwd: str) -> Path:
    path = Path(cwd).resolve() / ".zero_os" / "assistant" / "jobs.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(json.dumps({"jobs": [], "recurring_jobs": []}, indent=2) + "\n", encoding="utf-8")
    return path


def _load(cwd: str) -> dict:
    data = json.loads(_path(cwd).read_text(encoding="utf-8", errors="replace"))
    data.setdefault("jobs", [])
    data.setdefault("recurring_jobs", [])
    return data


def _save(cwd: str, data: dict) -> None:
    _path(cwd).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _parse_utc(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _recurring_due(job: dict) -> bool:
    if not bool(job.get("enabled", False)):
        return False
    last_run = _parse_utc(str(job.get("last_run_utc", "")))
    if last_run is None:
        return True
    interval = max(30, int(job.get("interval_seconds", 180)))
    now = datetime.now(timezone.utc)
    return (now - last_run).total_seconds() >= interval


def _builtin_result(cwd: str, name: str) -> dict:
    if name == "continuity_governance":
        return zero_ai_continuity_governance_tick(cwd)
    if name == "communications":
        return communications_tick(cwd)
    if name == "calendar_time":
        return calendar_reminder_tick(cwd)
    return {"ok": False, "reason": f"unknown builtin recurring job: {name}"}


def _recurring_summary(job: dict) -> dict:
    return {
        "id": job.get("id"),
        "name": job.get("name"),
        "kind": job.get("kind"),
        "enabled": job.get("enabled", False),
        "interval_seconds": job.get("interval_seconds", 180),
        "last_run_utc": job.get("last_run_utc", ""),
        "last_result_ok": job.get("last_result_ok"),
        "last_result_ran": job.get("last_result_ran"),
        "last_reason": job.get("last_reason", ""),
        "attempts": job.get("attempts", 0),
        "request": job.get("request", ""),
    }


def schedule(cwd: str, request: str) -> dict:
    data = _load(cwd)
    job = {"id": str(uuid.uuid4())[:10], "request": request, "state": "queued", "created_utc": _utc_now(), "attempts": 0}
    data.setdefault("jobs", []).append(job)
    _save(cwd, data)
    return {"ok": True, "job": job}


def schedule_recurring_builtin(cwd: str, name: str, interval_seconds: int = 180, enabled: bool = True) -> dict:
    data = _load(cwd)
    recurring = data.setdefault("recurring_jobs", [])
    existing = next((job for job in recurring if job.get("name") == name and job.get("kind") == "builtin"), None)
    if existing is None:
        existing = {
            "id": str(uuid.uuid4())[:10],
            "name": name,
            "kind": "builtin",
            "enabled": bool(enabled),
            "interval_seconds": max(30, int(interval_seconds)),
            "created_utc": _utc_now(),
            "last_run_utc": "",
            "last_result_ok": None,
            "last_result_ran": None,
            "last_reason": "",
            "attempts": 0,
            "request": "",
        }
        recurring.append(existing)
    else:
        existing["enabled"] = bool(enabled)
        existing["interval_seconds"] = max(30, int(interval_seconds))
    _save(cwd, data)
    return {"ok": True, "recurring_job": _recurring_summary(existing)}


def remove_recurring(cwd: str, name: str) -> dict:
    data = _load(cwd)
    recurring = data.setdefault("recurring_jobs", [])
    kept = [job for job in recurring if job.get("name") != name]
    removed = len(recurring) - len(kept)
    data["recurring_jobs"] = kept
    _save(cwd, data)
    return {"ok": True, "removed": removed, "name": name}


def recurring_builtin_status(cwd: str, name: str) -> dict:
    data = _load(cwd)
    recurring = next((job for job in data.get("recurring_jobs", []) if job.get("name") == name), None)
    governance = zero_ai_continuity_governance_status(cwd) if name == "continuity_governance" else None
    return {
        "ok": True,
        "name": name,
        "auto": zero_ai_continuity_governance_auto_status(cwd) if name == "continuity_governance" else None,
        "continuity_governance": governance,
        "recurring_job": _recurring_summary(recurring) if recurring else None,
        "jobs": status(cwd),
    }


def recurring_builtin_auto_apply(cwd: str, name: str) -> dict:
    if name != "continuity_governance":
        return {"ok": False, "reason": f"unknown builtin recurring job: {name}"}

    auto = zero_ai_continuity_governance_auto_status(cwd)
    if bool(auto.get("recommended_enabled", False)):
        interval = int(auto.get("recommended_interval_seconds", 180))
        zero_ai_continuity_governance_set(cwd, True, interval)
        job_change = schedule_recurring_builtin(cwd, name, interval_seconds=interval, enabled=True)
    else:
        zero_ai_continuity_governance_set(cwd, False, None)
        job_change = remove_recurring(cwd, name)

    return {
        "ok": True,
        "auto": zero_ai_continuity_governance_auto_status(cwd),
        "continuity_governance": zero_ai_continuity_governance_status(cwd),
        "job_change": job_change,
        "jobs": status(cwd),
    }


def tick_recurring_builtin(cwd: str, name: str, force: bool = False) -> dict:
    data = _load(cwd)
    recurring = next((job for job in data.get("recurring_jobs", []) if job.get("name") == name and job.get("kind") == "builtin"), None)
    if recurring is None:
        return {"ok": True, "ticked": False, "reason": f"recurring job not scheduled: {name}"}
    if not bool(recurring.get("enabled", False)):
        return {"ok": True, "ticked": False, "reason": f"recurring job disabled: {name}", "recurring_job": _recurring_summary(recurring)}
    if not force and not _recurring_due(recurring):
        return {"ok": True, "ticked": False, "reason": f"recurring job not due: {name}", "recurring_job": _recurring_summary(recurring)}

    recurring["attempts"] = int(recurring.get("attempts", 0)) + 1
    result = _builtin_result(cwd, str(recurring.get("name", "")))
    recurring["last_run_utc"] = _utc_now()
    recurring["last_result_ok"] = bool(result.get("ok", False))
    recurring["last_result_ran"] = bool(result.get("ran", result.get("ok", False)))
    recurring["last_reason"] = str(result.get("reason", ""))
    _save(cwd, data)
    return {"ok": True, "ticked": True, "recurring_job": _recurring_summary(recurring), "result": result}


def status(cwd: str) -> dict:
    data = _load(cwd)
    recurring = [_recurring_summary(job) for job in data.get("recurring_jobs", [])]
    return {
        "ok": True,
        "count": len(data.get("jobs", [])),
        "jobs": data.get("jobs", [])[-20:],
        "recurring_count": len(recurring),
        "recurring_jobs": recurring[-20:],
    }


def tick(cwd: str) -> dict:
    data = _load(cwd)
    for job in data.get("jobs", []):
        if job.get("state") == "queued":
            job["state"] = "running"
            job["attempts"] = int(job.get("attempts", 0)) + 1
            result = run_task(cwd, str(job.get("request", "")))
            job["state"] = "done" if result.get("ok", False) else "needs_resume"
            job["last_run_utc"] = _utc_now()
            job["result_ok"] = bool(result.get("ok", False))
            _save(cwd, data)
            return {"ok": True, "job": job, "result": result}
        if job.get("state") == "needs_resume":
            job["state"] = "running"
            job["attempts"] = int(job.get("attempts", 0)) + 1
            result = run_task_resume(cwd)
            job["state"] = "done" if result.get("ok", False) else "needs_resume"
            job["last_run_utc"] = _utc_now()
            job["result_ok"] = bool(result.get("ok", False))
            _save(cwd, data)
            return {"ok": True, "job": job, "result": result}
    for recurring in data.get("recurring_jobs", []):
        if not _recurring_due(recurring):
            continue
        return tick_recurring_builtin(cwd, str(recurring.get("name", "")), force=True)
    return {"ok": False, "reason": "no runnable jobs"}
