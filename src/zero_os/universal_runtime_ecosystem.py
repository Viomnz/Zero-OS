from __future__ import annotations

import json
import platform
from datetime import datetime, timezone
from pathlib import Path

from zero_os.app_store_universal import detect_device, resolve_package


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _state_path(cwd: str) -> Path:
    p = Path(cwd).resolve() / ".zero_os" / "runtime" / "universal_runtime_ecosystem.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _default_state() -> dict:
    return {
        "runtime": {
            "installed": False,
            "version": "0.1",
            "api_translation": True,
            "sandbox": True,
            "hardware_abstraction": True,
            "resource_management": True,
            "compat_runtime": ["wasm", "container", "compat-layer", "virtualization"],
        },
        "adapters": {
            "windows": "WinAdapter",
            "linux": "LinuxAdapter",
            "macos": "MacAdapter",
            "android": "AndroidAdapter",
            "ios": "iOSAdapter",
        },
        "security": {
            "runtime_sandbox": "enabled",
            "permission_engine": "enabled",
            "digital_signature": "required",
            "malware_scanning": "enabled",
            "runtime_behavior_monitor": "enabled",
        },
        "infrastructure": {
            "global_registry": "online",
            "developer_upload_gateway": "online",
            "validation_engine": "online",
            "package_storage_cluster": "online",
            "compatibility_engine": "online",
            "cdn": "online",
        },
        "coverage": [
            "desktop computers",
            "smartphones",
            "tablets",
            "game consoles",
            "VR headsets",
            "smart TVs",
            "embedded systems",
        ],
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


def runtime_install(cwd: str, version: str = "0.1") -> dict:
    s = _load(cwd)
    s["runtime"]["installed"] = True
    s["runtime"]["version"] = version.strip() or "0.1"
    _save(cwd, s)
    return {"ok": True, "runtime": s["runtime"]}


def runtime_status(cwd: str) -> dict:
    s = _load(cwd)
    return {"ok": True, "runtime": s["runtime"], "updated_utc": s.get("updated_utc", "")}


def adapter_set(cwd: str, os_name: str, module_name: str) -> dict:
    s = _load(cwd)
    key = os_name.strip().lower()
    if key not in {"windows", "linux", "macos", "android", "ios"}:
        return {"ok": False, "reason": "os must be windows|linux|macos|android|ios"}
    s["adapters"][key] = module_name.strip()
    _save(cwd, s)
    return {"ok": True, "os": key, "adapter": s["adapters"][key]}


def adapters_status(cwd: str) -> dict:
    s = _load(cwd)
    host = platform.system().lower()
    host_os = "windows" if "windows" in host else "linux" if "linux" in host else "macos" if "darwin" in host else "unknown"
    return {"ok": True, "host_os": host_os, "adapters": s["adapters"]}


def execution_flow(cwd: str, app_name: str, target_os: str = "") -> dict:
    s = _load(cwd)
    device = detect_device()
    if target_os:
        device["os"] = target_os.strip().lower()
    resolved = resolve_package(cwd, app_name, device["os"], device["cpu"], device["architecture"], device["security"])
    if not resolved.get("ok", False):
        return {"ok": False, "device": device, "resolve": resolved}
    os_name = resolved["os"]
    adapter = s["adapters"].get(os_name, "UnknownAdapter")
    return {
        "ok": True,
        "flow": {
            "application": app_name,
            "universal_runtime": s["runtime"]["version"],
            "os_adapter": adapter,
            "host_os": device["os"],
            "delivery": resolved.get("delivery", "native"),
        },
        "resolve": resolved,
    }


def security_status(cwd: str) -> dict:
    s = _load(cwd)
    return {"ok": True, "security": s["security"]}


def infrastructure_status(cwd: str) -> dict:
    s = _load(cwd)
    return {"ok": True, "infrastructure": s["infrastructure"]}


def coverage_status(cwd: str) -> dict:
    s = _load(cwd)
    return {"ok": True, "coverage": s["coverage"]}
