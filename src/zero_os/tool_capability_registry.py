from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _runtime_dir(cwd: str) -> Path:
    path = Path(cwd).resolve() / ".zero_os" / "runtime"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _status_path(cwd: str) -> Path:
    return _runtime_dir(cwd) / "tool_capability_registry.json"


def capability_registry() -> dict:
    return {
        "local_files": {
            "label": "Local files",
            "enabled": True,
            "risk": "medium",
            "actions": ["read", "write", "merge", "inspect"],
        },
        "web_lookup": {
            "label": "Web lookup",
            "enabled": True,
            "risk": "medium",
            "actions": ["search", "fetch", "validate"],
        },
        "shell": {
            "label": "Shell",
            "enabled": True,
            "risk": "high",
            "actions": ["run", "inspect"],
        },
        "system_runtime": {
            "label": "System runtime",
            "enabled": True,
            "risk": "medium",
            "actions": ["status", "recover", "repair", "security", "platform"],
        },
        "browser_automation": {
            "label": "Browser automation",
            "enabled": True,
            "risk": "medium",
            "actions": ["open", "inspect", "click", "input"],
        },
        "api_profiles": {
            "label": "API profiles",
            "enabled": True,
            "risk": "medium",
            "actions": ["configure", "request", "workflow"],
        },
        "recovery": {
            "label": "Recovery snapshots",
            "enabled": True,
            "risk": "high",
            "actions": ["backup", "restore", "inventory"],
        },
        "native_store": {
            "label": "Native store",
            "enabled": True,
            "risk": "high",
            "actions": ["install", "upgrade", "rollback", "release"],
        },
        "backend_ops": {
            "label": "Backend operations",
            "enabled": True,
            "risk": "high",
            "actions": ["backup", "restore", "deploy", "status"],
        },
    }


def _nonempty_profiles(path: Path) -> tuple[bool, int]:
    if not path.exists():
        return False, 0
    try:
        payload = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return False, 0
    profiles = payload.get("profiles", {}) if isinstance(payload, dict) else {}
    if not isinstance(profiles, dict):
        return False, 0
    return len(profiles) > 0, len(profiles)


def _tool_state(base: Path, key: str) -> tuple[bool, list[str], dict]:
    runtime_file = base / ".zero_os" / "runtime" / "phase_runtime_status.json"
    snapshots_dir = base / ".zero_os" / "production" / "snapshots"
    profiles_path = base / ".zero_os" / "connectors" / "api_profiles.json"
    browser_state = base / ".zero_os" / "connectors" / "browser_session.json"
    apps_root = base / "apps"
    workflows_root = base / ".github" / "workflows"

    if key == "local_files":
        active = (base / "src" / "main.py").exists() and (base / "README.md").exists()
        return active, ([] if active else ["workspace source baseline missing"]), {"main_py": str(base / "src" / "main.py")}
    if key == "web_lookup":
        active = True
        return active, [], {"connector": "http_ready"}
    if key == "shell":
        active = True
        return active, [], {"connector": "local_shell"}
    if key == "system_runtime":
        active = runtime_file.exists()
        return active, ([] if active else ["runtime status baseline missing"]), {"status_path": str(runtime_file)}
    if key == "browser_automation":
        connectors_root = base / ".zero_os" / "connectors"
        active = browser_state.exists() or connectors_root.exists()
        return active, ([] if active else ["browser session baseline missing"]), {"session_path": str(browser_state)}
    if key == "api_profiles":
        active, count = _nonempty_profiles(profiles_path)
        return active, ([] if active else ["no reusable API profile configured"]), {"profile_count": count, "path": str(profiles_path)}
    if key == "recovery":
        active = snapshots_dir.exists() and any(snapshots_dir.rglob("*"))
        return active, ([] if active else ["baseline recovery snapshot missing"]), {"snapshot_dir": str(snapshots_dir)}
    if key == "native_store":
        active = (apps_root.exists() and any(apps_root.iterdir())) or (base / ".zero_os" / "native_store" / "state.json").exists()
        return active, ([] if active else ["store install target package missing"]), {"apps_root": str(apps_root)}
    if key == "backend_ops":
        active = workflows_root.exists() or (base / "build" / "native_store_prod" / "backend_deploy").exists()
        return active, ([] if active else ["backend operations baseline missing"]), {"workflows_root": str(workflows_root)}
    return False, ["unknown tool"], {}


def _highest_value_steps(missing_tools: list[dict]) -> list[str]:
    missing_keys = {str(item.get("tool", "")) for item in missing_tools}
    steps: list[str] = []
    if "recovery" in missing_keys:
        steps.append("Create a baseline recovery snapshot so Zero AI can restore from a known-good point immediately.")
    if "native_store" in missing_keys:
        steps.append("Publish or scaffold at least one app package so install workflows have a real target.")
    if "api_profiles" in missing_keys:
        steps.append("Configure at least one reusable API profile so typed external workflows can run cleanly.")
    if "system_runtime" in missing_keys:
        steps.append("Write a runtime baseline so Zero AI can report and schedule its system loop honestly.")
    if not steps:
        steps.append("Keep tool baselines healthy and refresh the registry after major workspace changes.")
    return steps


def registry_status(cwd: str = "") -> dict:
    base = Path(cwd or ".").resolve()
    registry = capability_registry()
    tools: dict[str, dict] = {}
    missing_tools: list[dict] = []

    for key, spec in registry.items():
        active, gaps, evidence = _tool_state(base, key)
        tool_entry = {
            **dict(spec),
            "key": key,
            "active": bool(active),
            "gaps": list(gaps),
            "evidence": dict(evidence),
        }
        tools[key] = tool_entry
        if gaps:
            missing_tools.append(
                {
                    "tool": key,
                    "label": str(spec.get("label", key)),
                    "gaps": list(gaps),
                }
            )

    summary = {
        "tool_count": len(tools),
        "active_tool_count": sum(1 for item in tools.values() if item.get("active")),
        "missing_tool_count": len(missing_tools),
    }
    payload = {
        "ok": True,
        "time_utc": _utc_now(),
        "path": str(_status_path(str(base))),
        "tools": tools,
        "summary": summary,
        "missing_tools": missing_tools,
        "highest_value_steps": _highest_value_steps(missing_tools),
    }
    _status_path(str(base)).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload
