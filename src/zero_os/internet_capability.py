from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from zero_os.api_connector_profiles import profile_status as api_profile_status
from zero_os.browser_session_connector import browser_session_status
from zero_os.github_integration_pack import status as github_status


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _assistant_dir(cwd: str) -> Path:
    path = Path(cwd).resolve() / ".zero_os" / "assistant"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _path(cwd: str) -> Path:
    return _assistant_dir(cwd) / "internet_capability.json"


def _load(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return dict(default)
    try:
        raw = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return dict(default)
    if not isinstance(raw, dict):
        return dict(default)
    merged = dict(default)
    merged.update(raw)
    return merged


def _save(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _default_state() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "last_refresh_utc": "",
        "last_report": {},
        "history": [],
    }


def internet_capability_status(cwd: str) -> dict[str, Any]:
    browser = browser_session_status(cwd)
    profiles = api_profile_status(cwd)
    github = github_status(cwd)
    profile_map = dict(profiles.get("profiles") or {})
    page_memory = dict(browser.get("page_memory") or {})
    browser_connected = bool(browser.get("tabs")) or bool(page_memory) or bool(str(browser.get("last_opened", "")).strip())
    connected_surfaces = 0
    if browser_connected:
        connected_surfaces += 1
    if len(profile_map) > 0:
        connected_surfaces += 1
    if bool(github.get("connected", False)):
        connected_surfaces += 1
    report = {
        "ok": True,
        "active": True,
        "ready": True,
        "browser": {
            "tab_count": len(browser.get("tabs", [])),
            "last_opened": str(browser.get("last_opened", "")),
            "remembered_page_count": len(page_memory),
            "connected": browser_connected,
        },
        "api_profiles": {
            "count": len(profile_map),
            "names": list(profile_map.keys())[:12],
        },
        "github": {
            "connected": bool(github.get("connected", False)),
            "repo": str(github.get("repo", "")),
        },
        "internet_modes": {
            "search_fetch": True,
            "browser_automation": True,
            "api_connectors": True,
            "github_integration": True,
        },
        "summary": {
            "connected_surface_count": connected_surfaces,
            "internet_ready": True,
        },
        "highest_value_steps": [
            "Use `search <query>` or `fetch <url>` for direct web lookups.",
            "Use `open <url>` or `inspect page <url>` for browser-backed internet actions.",
            "Use `zero ai api profile set ...` to add typed external API access.",
        ],
    }
    state = _load(_path(cwd), _default_state())
    state["last_refresh_utc"] = _utc_now()
    state["last_report"] = report
    history = list(state.get("history", []))
    history.append(
        {
            "time_utc": state["last_refresh_utc"],
            "connected_surface_count": connected_surfaces,
            "profile_count": report["api_profiles"]["count"],
            "github_connected": report["github"]["connected"],
        }
    )
    state["history"] = history[-20:]
    _save(_path(cwd), state)
    report["path"] = str(_path(cwd))
    report["last_refresh_utc"] = state["last_refresh_utc"]
    return report


def internet_capability_refresh(cwd: str) -> dict[str, Any]:
    return internet_capability_status(cwd)
