from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _state_path(cwd: str) -> Path:
    p = Path(cwd).resolve() / ".zero_os" / "runtime" / "global_runtime_network.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _default_state() -> dict:
    return {
        "registry": {"global": "online", "regional_hubs": ["us-west", "us-east", "eu-central"]},
        "nodes": {},
        "cache": {"entries": {}},
        "runtime_release": {"version": "1.0.0", "last_propagation_utc": ""},
        "security": {"signature_validation": "enabled", "encrypted_links": "enabled", "behavior_monitoring": "enabled"},
        "telemetry": {"events": [], "performance_feedback": {}},
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


def _event(state: dict, typ: str, payload: dict) -> None:
    state["telemetry"]["events"].append({"time_utc": _utc_now(), "type": typ, "payload": payload})
    state["telemetry"]["events"] = state["telemetry"]["events"][-300:]


def node_register(cwd: str, os_name: str, device_class: str, mode: str) -> dict:
    s = _load(cwd)
    nid = str(uuid.uuid4())[:12]
    rec = {"node_id": nid, "os": os_name.lower(), "device_class": device_class.lower(), "execution_mode": mode.lower(), "runtime_version": s["runtime_release"]["version"], "registered_utc": _utc_now()}
    s["nodes"][nid] = rec
    _event(s, "node_register", rec)
    _save(cwd, s)
    return {"ok": True, "node": rec}


def node_discovery(cwd: str, os_name: str = "") -> dict:
    s = _load(cwd)
    nodes = list(s["nodes"].values())
    if os_name:
        nodes = [n for n in nodes if n["os"] == os_name.lower()]
    return {"ok": True, "total": len(nodes), "nodes": nodes}


def cache_put(cwd: str, app: str, version: str, region: str) -> dict:
    s = _load(cwd)
    key = f"{app}:{version}:{region}"
    s["cache"]["entries"][key] = {"app": app, "version": version, "region": region, "cached_utc": _utc_now()}
    _event(s, "cache_put", {"key": key})
    _save(cwd, s)
    return {"ok": True, "cache_key": key}


def cache_status(cwd: str) -> dict:
    s = _load(cwd)
    return {"ok": True, "total": len(s["cache"]["entries"]), "entries": s["cache"]["entries"]}


def runtime_release_propagate(cwd: str, version: str) -> dict:
    s = _load(cwd)
    s["runtime_release"]["version"] = version
    s["runtime_release"]["last_propagation_utc"] = _utc_now()
    for nid in s["nodes"]:
        s["nodes"][nid]["runtime_version"] = version
    _event(s, "runtime_propagate", {"version": version, "nodes": len(s["nodes"])})
    _save(cwd, s)
    return {"ok": True, "version": version, "node_count": len(s["nodes"])}


def security_validate(cwd: str, signed: bool) -> dict:
    s = _load(cwd)
    ok = bool(signed)
    _event(s, "security_validate", {"signed": bool(signed), "ok": ok})
    _save(cwd, s)
    return {"ok": ok, "checks": s["security"], "signed": bool(signed)}


def adaptive_mode(cwd: str, device_class: str) -> dict:
    cls = device_class.lower()
    if "desktop" in cls:
        mode = "jit-native"
    elif "smartphone" in cls or "mobile" in cls:
        mode = "optimized-bytecode"
    elif "embedded" in cls:
        mode = "lightweight-runtime"
    elif "server" in cls:
        mode = "container-runtime"
    else:
        mode = "portable-bytecode"
    s = _load(cwd)
    s["telemetry"]["performance_feedback"][cls] = mode
    _event(s, "adaptive_mode", {"device_class": cls, "mode": mode})
    _save(cwd, s)
    return {"ok": True, "device_class": cls, "execution_mode": mode}


def network_status(cwd: str) -> dict:
    s = _load(cwd)
    return {
        "ok": True,
        "registry": s["registry"],
        "runtime_release": s["runtime_release"],
        "node_total": len(s["nodes"]),
        "cache_total": len(s["cache"]["entries"]),
        "security": s["security"],
    }


def telemetry_status(cwd: str) -> dict:
    s = _load(cwd)
    return {"ok": True, "telemetry": s["telemetry"]}
