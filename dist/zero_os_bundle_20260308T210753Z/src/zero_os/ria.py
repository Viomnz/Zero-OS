from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _state_path(cwd: str) -> Path:
    p = Path(cwd).resolve() / ".zero_os" / "runtime" / "ria_state.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _default_state() -> dict:
    return {
        "instruction_groups": {
            "compute": ["EXECUTE_COMPUTE", "ARITH_ADD", "LOGIC_AND"],
            "memory": ["ALLOC_MEMORY", "WRITE_MEMORY", "READ_MEMORY", "TRANSFER_MEMORY"],
            "graphics": ["GPU_RENDER", "GPU_DISPATCH"],
            "network": ["SYNC_NETWORK", "SEND_PACKET", "RECV_PACKET"],
            "capability": ["VERIFY_CAPABILITY", "ASSERT_TOKEN"],
            "resource": ["LOAD_RESOURCE"],
        },
        "programs": {},
        "exec_history": [],
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
    _state_path(cwd).write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def status(cwd: str) -> dict:
    s = _load(cwd)
    return {"ok": True, "instruction_groups": s["instruction_groups"], "programs": len(s["programs"]), "executions": len(s["exec_history"])}


def _instruction_set(s: dict) -> set[str]:
    out: set[str] = set()
    for arr in s["instruction_groups"].values():
        for x in arr:
            out.add(x)
    return out


def program_register(cwd: str, app: str, instructions_json: str) -> dict:
    s = _load(cwd)
    try:
        data = json.loads(instructions_json)
    except Exception:
        return {"ok": False, "reason": "invalid instructions json"}
    if not isinstance(data, list) or not data:
        return {"ok": False, "reason": "instructions must be non-empty list"}
    allowed = _instruction_set(s)
    bad = [x for x in data if str(x).upper() not in allowed]
    if bad:
        return {"ok": False, "reason": "unknown instructions", "invalid": bad}
    pid = str(uuid.uuid4())[:12]
    s["programs"][pid] = {"app": app.strip(), "instructions": [str(x).upper() for x in data], "registered_utc": _utc_now()}
    _save(cwd, s)
    return {"ok": True, "program_id": pid}


def program_validate(cwd: str, program_id: str) -> dict:
    s = _load(cwd)
    p = s["programs"].get(program_id)
    if not p:
        return {"ok": False, "reason": "program not found"}
    allowed = _instruction_set(s)
    bad = [x for x in p["instructions"] if x not in allowed]
    return {"ok": len(bad) == 0, "program_id": program_id, "invalid": bad}


def execute(cwd: str, program_id: str, capabilities_json: str = "{}") -> dict:
    s = _load(cwd)
    p = s["programs"].get(program_id)
    if not p:
        return {"ok": False, "reason": "program not found"}
    try:
        caps = json.loads(capabilities_json) if capabilities_json else {}
    except Exception:
        caps = {}
    token_ok = bool(caps.get("token", False))
    steps = []
    for ins in p["instructions"]:
        if ins in {"VERIFY_CAPABILITY", "ASSERT_TOKEN"} and not token_ok:
            return {"ok": False, "reason": "capability verification failed", "instruction": ins}
        steps.append({"instruction": ins, "result": "ok"})
    rec = {"time_utc": _utc_now(), "program_id": program_id, "app": p["app"], "steps": steps}
    s["exec_history"].append(rec)
    s["exec_history"] = s["exec_history"][-500:]
    _save(cwd, s)
    return {"ok": True, "execution": rec}
