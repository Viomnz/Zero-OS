from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from zero_os.task_executor import run_task, run_task_resume


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _path(cwd: str) -> Path:
    path = Path(cwd).resolve() / ".zero_os" / "assistant" / "jobs.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(json.dumps({"jobs": []}, indent=2) + "\n", encoding="utf-8")
    return path


def _load(cwd: str) -> dict:
    return json.loads(_path(cwd).read_text(encoding="utf-8", errors="replace"))


def _save(cwd: str, data: dict) -> None:
    _path(cwd).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def schedule(cwd: str, request: str) -> dict:
    data = _load(cwd)
    job = {"id": str(uuid.uuid4())[:10], "request": request, "state": "queued", "created_utc": _utc_now(), "attempts": 0}
    data.setdefault("jobs", []).append(job)
    _save(cwd, data)
    return {"ok": True, "job": job}


def status(cwd: str) -> dict:
    data = _load(cwd)
    return {"ok": True, "count": len(data.get("jobs", [])), "jobs": data.get("jobs", [])[-20:]}


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
    return {"ok": False, "reason": "no runnable jobs"}
