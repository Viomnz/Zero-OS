"""Persistent runtime state for Zero-OS."""

from __future__ import annotations

import json
from pathlib import Path


DEFAULT_MODE = "casual"
SUPPORTED_MODES = {"casual", "heavy"}
SUPPORTED_PROFILES = {"auto", "low", "balanced", "high"}


def _state_path(cwd: str) -> Path:
    return Path(cwd).resolve() / ".zero_os" / "state.json"


def get_mode(cwd: str) -> str:
    path = _state_path(cwd)
    if not path.exists():
        return DEFAULT_MODE
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except json.JSONDecodeError:
        return DEFAULT_MODE
    mode = str(data.get("user_mode", DEFAULT_MODE)).lower()
    return mode if mode in SUPPORTED_MODES else DEFAULT_MODE


def set_mode(cwd: str, mode: str) -> str:
    normalized = mode.lower().strip()
    if normalized not in SUPPORTED_MODES:
        raise ValueError(f"Unsupported mode: {mode}")
    path = _state_path(cwd)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, str] = {}
    if path.exists():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8", errors="replace"))
            if isinstance(loaded, dict):
                payload = {k: str(v) for k, v in loaded.items()}
        except json.JSONDecodeError:
            payload = {}
    payload["user_mode"] = normalized
    if "performance_profile" not in payload:
        payload["performance_profile"] = "auto"
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return normalized


def get_profile_setting(cwd: str) -> str:
    path = _state_path(cwd)
    if not path.exists():
        return "auto"
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except json.JSONDecodeError:
        return "auto"
    value = str(data.get("performance_profile", "auto")).lower()
    return value if value in SUPPORTED_PROFILES else "auto"


def set_profile_setting(cwd: str, profile: str) -> str:
    normalized = profile.lower().strip()
    if normalized not in SUPPORTED_PROFILES:
        raise ValueError(f"Unsupported profile: {profile}")
    path = _state_path(cwd)
    path.parent.mkdir(parents=True, exist_ok=True)
    data: dict[str, str] = {}
    if path.exists():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8", errors="replace"))
            if isinstance(loaded, dict):
                data = {k: str(v) for k, v in loaded.items()}
        except json.JSONDecodeError:
            data = {}
    data["performance_profile"] = normalized
    if "user_mode" not in data:
        data["user_mode"] = DEFAULT_MODE
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return normalized


def get_mark_strict(cwd: str) -> bool:
    path = _state_path(cwd)
    if not path.exists():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except json.JSONDecodeError:
        return False
    return bool(data.get("mark_strict", False))


def set_mark_strict(cwd: str, enabled: bool) -> bool:
    path = _state_path(cwd)
    path.parent.mkdir(parents=True, exist_ok=True)
    data: dict[str, str | bool] = {}
    if path.exists():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8", errors="replace"))
            if isinstance(loaded, dict):
                data = loaded
        except json.JSONDecodeError:
            data = {}
    if "user_mode" not in data:
        data["user_mode"] = DEFAULT_MODE
    if "performance_profile" not in data:
        data["performance_profile"] = "auto"
    data["mark_strict"] = bool(enabled)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return bool(enabled)


def get_net_strict(cwd: str) -> bool:
    path = _state_path(cwd)
    if not path.exists():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except json.JSONDecodeError:
        return False
    return bool(data.get("net_strict", False))


def set_net_strict(cwd: str, enabled: bool) -> bool:
    path = _state_path(cwd)
    path.parent.mkdir(parents=True, exist_ok=True)
    data: dict[str, str | bool] = {}
    if path.exists():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8", errors="replace"))
            if isinstance(loaded, dict):
                data = loaded
        except json.JSONDecodeError:
            data = {}
    if "user_mode" not in data:
        data["user_mode"] = DEFAULT_MODE
    if "performance_profile" not in data:
        data["performance_profile"] = "auto"
    data["net_strict"] = bool(enabled)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return bool(enabled)
