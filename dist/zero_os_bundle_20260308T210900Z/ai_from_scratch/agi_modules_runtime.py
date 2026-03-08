from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


REGISTRY_PATH = Path("zero_os_config") / "agi_module_registry.json"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_registry(cwd: str) -> dict:
    p = Path(cwd).resolve() / REGISTRY_PATH
    raw = json.loads(p.read_text(encoding="utf-8", errors="replace"))
    if not isinstance(raw, dict):
        raise ValueError("invalid registry")
    return raw


def list_module_ids(cwd: str) -> list[str]:
    reg = _load_registry(cwd)
    modules = reg.get("modules", [])
    if not isinstance(modules, list):
        return []
    out = []
    for m in modules:
        if isinstance(m, dict):
            mid = str(m.get("id", "")).strip()
            if mid:
                out.append(mid)
    return out


def run_module(cwd: str, module_id: str, context: dict | None = None) -> dict:
    reg = _load_registry(cwd)
    modules = reg.get("modules", [])
    info = None
    for m in modules:
        if isinstance(m, dict) and str(m.get("id", "")).strip() == module_id:
            info = m
            break
    if info is None:
        return {
            "ok": False,
            "module_id": module_id,
            "reason": "module_not_found",
            "time_utc": _utc_now(),
        }
    payload = {
        "ok": True,
        "module_id": module_id,
        "module_name": info.get("name", ""),
        "domain": info.get("domain", ""),
        "status": info.get("status", "planned"),
        "mode": "deterministic-runtime-fallback",
        "decision": "safe_state_continue",
        "metrics": {
            "input_keys": sorted(list((context or {}).keys())),
            "context_size": len(context or {}),
        },
        "trace": {
            "engine": "agi_modules_runtime_v1",
            "time_utc": _utc_now(),
        },
    }
    return payload
