from __future__ import annotations

import hashlib
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


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _trigger_class(trigger: str) -> str:
    t = str(trigger or "").strip().lower()
    if t in {"manual_stop", "manual_request"}:
        return "manual_request"
    if t in {"maintenance", "scheduled_maintenance", "update"}:
        return "maintenance"
    if t in {"resource_exhaustion", "resource_limit", "out_of_memory"}:
        return "resource_exhaustion"
    if t in {"critical_failure", "contained", "compromised", "eliminated"}:
        return "critical_failure"
    return "other"


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
    trace = rt / "decision_trace.json"
    trace_snapshot = rt / "recovery_trace_snapshot.json"
    if mem.exists():
        shutil.copy2(mem, mem_snapshot)
    if trace.exists():
        shutil.copy2(trace, trace_snapshot)

    output = rt / "zero_ai_output.txt"
    tasks = rt / "zero_ai_tasks.txt"
    trigger_class = _trigger_class(trigger)
    state_snapshot = {
        "runtime_status": {
            "queue_size": int(queue_size),
            "checkpoint_loaded": bool(checkpoint_loaded),
            "output_exists": output.exists(),
            "tasks_exists": tasks.exists(),
        },
        "shutdown_class": trigger_class,
        "reason": reason,
    }
    payload = {
        "time_utc": _utc_now(),
        "trigger": trigger,
        "trigger_class": trigger_class,
        "reason": reason,
        "queue_size": int(queue_size),
        "checkpoint_loaded": bool(checkpoint_loaded),
        "controlled_shutdown_process": {
            "stop_execution": True,
            "preserve_state": True,
            "protect_data": True,
            "power_down_modules": True,
        },
        "files": {
            "memory_snapshot": str(mem_snapshot) if mem_snapshot.exists() else "",
            "trace_snapshot": str(trace_snapshot) if trace_snapshot.exists() else "",
            "output_exists": output.exists(),
            "tasks_exists": tasks.exists(),
            "output_kb": int(output.stat().st_size / 1024) if output.exists() else 0,
            "memory_snapshot_sha256": _sha256(mem_snapshot) if mem_snapshot.exists() else "",
            "trace_snapshot_sha256": _sha256(trace_snapshot) if trace_snapshot.exists() else "",
        },
        "state_snapshot": state_snapshot,
        "recovery_steps": {
            "system_restart": True,
            "integrity_verification": True,
            "state_restoration": True,
            "resume_operation": True,
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


def verify_recovery_integrity(cwd: str) -> dict:
    loaded = load_recovery_state(cwd)
    if not loaded.get("found"):
        return {"ok": False, "reason": "recovery state missing"}
    state = loaded.get("state", {})
    files = state.get("files", {}) if isinstance(state, dict) else {}
    mem_path = str(files.get("memory_snapshot", "")).strip()
    trace_path = str(files.get("trace_snapshot", "")).strip()
    checks = {
        "memory_snapshot_exists": (not mem_path) or Path(mem_path).exists(),
        "trace_snapshot_exists": (not trace_path) or Path(trace_path).exists(),
        "state_snapshot_present": isinstance(state.get("state_snapshot", {}), dict),
        "shutdown_steps_present": isinstance(state.get("controlled_shutdown_process", {}), dict),
        "recovery_steps_present": isinstance(state.get("recovery_steps", {}), dict),
    }
    ok = all(checks.values())
    return {"ok": ok, "checks": checks, "trigger_class": state.get("trigger_class", "other")}
