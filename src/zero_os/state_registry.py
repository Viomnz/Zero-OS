from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from zero_os.state_cache import flush_state_writes, load_json_state, queue_json_state

_REGISTRY: dict[str, dict[str, dict[str, Any]]] = {}


def _cwd_key(cwd: str) -> str:
    return str(Path(cwd).resolve())


def _store_specs(cwd: str) -> dict[str, dict[str, Any]]:
    base = Path(cwd).resolve()
    runtime = base / ".zero_os" / "runtime"
    assistant = base / ".zero_os" / "assistant"
    self_derivation = assistant / "self_derivation"
    pressure = assistant / "pressure_harness"
    return {
        "runtime_loop": {
            "path": runtime / "runtime_loop_state.json",
            "default": {},
            "hot": True,
        },
        "runtime_agent": {
            "path": runtime / "runtime_agent_state.json",
            "default": {},
            "hot": True,
        },
        "phase_runtime_status": {
            "path": runtime / "phase_runtime_status.json",
            "default": {},
            "hot": True,
        },
        "zero_engine_status": {
            "path": runtime / "zero_engine_status.json",
            "default": {},
            "hot": True,
        },
        "workspace_scan_snapshot": {
            "path": runtime / "workspace_scan_snapshot.json",
            "default": {},
            "hot": True,
        },
        "maintenance_state": {
            "path": assistant / "maintenance_orchestrator.json",
            "default": {},
            "hot": True,
        },
        "self_derivation_memory": {
            "path": self_derivation / "memory.json",
            "default": {},
            "hot": True,
        },
        "self_derivation_latest": {
            "path": self_derivation / "latest.json",
            "default": {},
            "hot": True,
        },
        "pressure_latest": {
            "path": pressure / "latest.json",
            "default": {},
            "hot": True,
        },
    }


def boot_state_registry(cwd: str, *, names: list[str] | None = None) -> dict[str, Any]:
    key = _cwd_key(cwd)
    specs = _store_specs(cwd)
    registry = _REGISTRY.setdefault(key, {})
    selected = names or [name for name, spec in specs.items() if bool(spec.get("hot", False))]
    loaded_names: list[str] = []
    for name in selected:
        spec = specs.get(name)
        if spec is None:
            continue
        payload = load_json_state(spec["path"], spec["default"])
        registry[name] = {
            "path": str(spec["path"]),
            "payload": deepcopy(payload),
            "default": deepcopy(spec["default"]),
            "hot": bool(spec.get("hot", False)),
        }
        loaded_names.append(name)
    return {
        "ok": True,
        "cwd": key,
        "loaded_count": len(loaded_names),
        "loaded_names": loaded_names,
    }


def get_state_store(cwd: str, name: str, default: Any = None) -> Any:
    key = _cwd_key(cwd)
    registry = _REGISTRY.setdefault(key, {})
    if name not in registry:
        boot_state_registry(cwd, names=[name])
    entry = registry.get(name)
    if entry is None:
        return deepcopy(default)
    return deepcopy(entry.get("payload", default))


def refresh_state_store(cwd: str, name: str) -> Any:
    specs = _store_specs(cwd)
    spec = specs.get(name)
    if spec is None:
        return {}
    payload = load_json_state(spec["path"], spec["default"])
    key = _cwd_key(cwd)
    registry = _REGISTRY.setdefault(key, {})
    registry[name] = {
        "path": str(spec["path"]),
        "payload": deepcopy(payload),
        "default": deepcopy(spec["default"]),
        "hot": bool(spec.get("hot", False)),
    }
    return deepcopy(payload)


def put_state_store(cwd: str, name: str, payload: Any, *, flush: bool = False) -> dict[str, Any]:
    specs = _store_specs(cwd)
    spec = specs.get(name)
    if spec is None:
        raise KeyError(f"unknown state store: {name}")
    key = _cwd_key(cwd)
    registry = _REGISTRY.setdefault(key, {})
    registry[name] = {
        "path": str(spec["path"]),
        "payload": deepcopy(payload),
        "default": deepcopy(spec["default"]),
        "hot": bool(spec.get("hot", False)),
    }
    queue_json_state(spec["path"], payload)
    flush_result = {"ok": True, "flushed_count": 0}
    if flush:
        flush_result = flush_state_writes(paths=[spec["path"]])
    return {
        "ok": True,
        "name": name,
        "path": str(spec["path"]),
        "flush": flush_result,
    }


def flush_state_registry(cwd: str, *, names: list[str] | None = None) -> dict[str, Any]:
    specs = _store_specs(cwd)
    selected_names = names or list(specs.keys())
    paths = [specs[name]["path"] for name in selected_names if name in specs]
    return flush_state_writes(paths=paths)


def state_registry_status(cwd: str) -> dict[str, Any]:
    key = _cwd_key(cwd)
    specs = _store_specs(cwd)
    registry = _REGISTRY.setdefault(key, {})
    stores: dict[str, Any] = {}
    for name, spec in specs.items():
        entry = dict(registry.get(name) or {})
        stores[name] = {
            "path": str(spec["path"]),
            "loaded": bool(entry),
            "hot": bool(spec.get("hot", False)),
            "payload_type": type(entry.get("payload")).__name__ if entry else "",
        }
    return {
        "ok": True,
        "cwd": key,
        "loaded_store_count": sum(1 for entry in stores.values() if bool(entry.get("loaded", False))),
        "stores": stores,
    }
