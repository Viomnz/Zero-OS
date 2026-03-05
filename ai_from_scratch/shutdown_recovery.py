from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _runtime(cwd: str) -> Path:
    p = Path(cwd).resolve() / ".zero_os" / "runtime"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _recovery_path(cwd: str) -> Path:
    return _runtime(cwd) / "recovery_state.json"


def prepare_shutdown_recovery(
    cwd: str,
    trigger: str,
    reason: str,
    queue_size: int,
    checkpoint_loaded: bool,
) -> dict:
    rt = _runtime(cwd)
    mem = rt / "internal_zero_reasoner_memory.json"
    mem_snapshot = rt / "recovery_memory_snapshot.json"
    if mem.exists():
        shutil.copy2(mem, mem_snapshot)

    output = rt / "zero_ai_output.txt"
    tasks = rt / "zero_ai_tasks.txt"
    payload = {
        "time_utc": _utc_now(),
        "trigger": trigger,
        "reason": reason,
        "queue_size": int(queue_size),
        "checkpoint_loaded": bool(checkpoint_loaded),
        "files": {
            "memory_snapshot": str(mem_snapshot) if mem_snapshot.exists() else "",
            "output_exists": output.exists(),
            "tasks_exists": tasks.exists(),
            "output_kb": int(output.stat().st_size / 1024) if output.exists() else 0,
        },
        "resume_hint": "load recovery state and continue normal operation",
    }
    _recovery_path(cwd).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def load_recovery_state(cwd: str) -> dict:
    p = _recovery_path(cwd)
    if not p.exists():
        return {"found": False, "state": {}}
    try:
        data = json.loads(p.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {"found": False, "state": {}, "error": "invalid recovery json"}
    return {"found": True, "state": data}

