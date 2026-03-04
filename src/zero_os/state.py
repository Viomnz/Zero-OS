"""Persistent runtime state for Zero-OS."""

from __future__ import annotations

import json
from pathlib import Path


DEFAULT_MODE = "casual"
SUPPORTED_MODES = {"casual", "heavy"}


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
    payload = {"user_mode": normalized}
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return normalized

