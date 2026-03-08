from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _state_path(cwd: str) -> Path:
    p = Path(cwd).resolve() / ".zero_os" / "runtime" / "platform_blueprint.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _default_state() -> dict:
    return {
        "problem_definition": {"completed": True, "notes": "OS fragmentation, dev cost, store fragmentation"},
        "core_architecture": {"completed": True},
        "runtime_instruction_set": {"completed": True},
        "app_package_format": {"completed": True},
        "runtime_engine": {"completed": True},
        "runtime_network": {"completed": True},
        "security_model": {"completed": True},
        "developer_toolchain": {"completed": True},
        "app_store": {"completed": True},
        "ecosystem_expansion": {"completed": True},
        "updated_utc": _utc_now(),
    }


def _load(cwd: str) -> dict:
    p = _state_path(cwd)
    if not p.exists():
        d = _default_state()
        _save(cwd, d)
        return d
    try:
        return json.loads(p.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        d = _default_state()
        _save(cwd, d)
        return d


def _save(cwd: str, state: dict) -> None:
    state["updated_utc"] = _utc_now()
    _state_path(cwd).write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def status(cwd: str) -> dict:
    s = _load(cwd)
    phases = [k for k in s.keys() if k != "updated_utc"]
    completed = sum(1 for k in phases if bool(s[k].get("completed", False)))
    score = round((completed / max(1, len(phases))) * 100, 2)
    return {
        "ok": True,
        "phase_total": len(phases),
        "phase_completed": completed,
        "completion_score": score,
        "phases": {k: s[k] for k in phases},
        "updated_utc": s.get("updated_utc", ""),
    }


def scaffold(cwd: str) -> dict:
    s = _load(cwd)
    for k in list(s.keys()):
        if k == "updated_utc":
            continue
        s[k]["completed"] = True
    _save(cwd, s)
    return {"ok": True, "status": status(cwd)}
