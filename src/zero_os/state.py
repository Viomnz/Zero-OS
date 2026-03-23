"""Persistent runtime state for Zero-OS."""

from __future__ import annotations

import json
from pathlib import Path

from zero_os.state_cache import flush_state_writes, load_json_state, queue_json_state


DEFAULT_MODE = "casual"
SUPPORTED_MODES = {"casual", "heavy"}
SUPPORTED_PROFILES = {
    "auto",
    "low",
    "balanced",
    "high",
    "tier1",
    "tier2",
    "tier3",
    "tier4",
}


def _state_path(cwd: str) -> Path:
    return Path(cwd).resolve() / ".zero_os" / "state.json"


def get_mode(cwd: str) -> str:
    path = _state_path(cwd)
    data = load_json_state(path, {})
    if not isinstance(data, dict):
        return DEFAULT_MODE
    mode = str(data.get("user_mode", DEFAULT_MODE)).lower()
    return mode if mode in SUPPORTED_MODES else DEFAULT_MODE


def set_mode(cwd: str, mode: str) -> str:
    normalized = mode.lower().strip()
    if normalized not in SUPPORTED_MODES:
        raise ValueError(f"Unsupported mode: {mode}")
    path = _state_path(cwd)
    payload: dict[str, str] = {}
    loaded = load_json_state(path, {})
    if isinstance(loaded, dict):
        payload = {k: str(v) for k, v in loaded.items()}
    payload["user_mode"] = normalized
    if "performance_profile" not in payload:
        payload["performance_profile"] = "auto"
    queue_json_state(path, payload)
    flush_state_writes(paths=[path])
    return normalized


def get_profile_setting(cwd: str) -> str:
    path = _state_path(cwd)
    data = load_json_state(path, {})
    if not isinstance(data, dict):
        return "auto"
    value = str(data.get("performance_profile", "auto")).lower()
    return value if value in SUPPORTED_PROFILES else "auto"


def set_profile_setting(cwd: str, profile: str) -> str:
    normalized = profile.lower().strip()
    if normalized not in SUPPORTED_PROFILES:
        raise ValueError(f"Unsupported profile: {profile}")
    path = _state_path(cwd)
    data: dict[str, str] = {}
    loaded = load_json_state(path, {})
    if isinstance(loaded, dict):
        data = {k: str(v) for k, v in loaded.items()}
    data["performance_profile"] = normalized
    if "user_mode" not in data:
        data["user_mode"] = DEFAULT_MODE
    queue_json_state(path, data)
    flush_state_writes(paths=[path])
    return normalized


def get_mark_strict(cwd: str) -> bool:
    path = _state_path(cwd)
    data = load_json_state(path, {})
    if not isinstance(data, dict):
        return False
    return bool(data.get("mark_strict", False))


def set_mark_strict(cwd: str, enabled: bool) -> bool:
    path = _state_path(cwd)
    data: dict[str, str | bool] = {}
    loaded = load_json_state(path, {})
    if isinstance(loaded, dict):
        data = loaded
    if "user_mode" not in data:
        data["user_mode"] = DEFAULT_MODE
    if "performance_profile" not in data:
        data["performance_profile"] = "auto"
    data["mark_strict"] = bool(enabled)
    queue_json_state(path, data)
    flush_state_writes(paths=[path])
    return bool(enabled)


def get_net_strict(cwd: str) -> bool:
    path = _state_path(cwd)
    data = load_json_state(path, {})
    if not isinstance(data, dict):
        return False
    return bool(data.get("net_strict", False))


def set_net_strict(cwd: str, enabled: bool) -> bool:
    path = _state_path(cwd)
    data: dict[str, str | bool] = {}
    loaded = load_json_state(path, {})
    if isinstance(loaded, dict):
        data = loaded
    if "user_mode" not in data:
        data["user_mode"] = DEFAULT_MODE
    if "performance_profile" not in data:
        data["performance_profile"] = "auto"
    data["net_strict"] = bool(enabled)
    queue_json_state(path, data)
    flush_state_writes(paths=[path])
    return bool(enabled)
