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


def _save(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _tool(
    label: str,
    *,
    enabled: bool,
    ready: bool,
    active: bool,
    risk: str,
    actions: list[str],
    commands: list[str],
    notes: str,
    gaps: list[str] | None = None,
) -> dict:
    return {
        "label": label,
        "enabled": bool(enabled),
        "ready": bool(ready),
        "active": bool(active),
        "risk": risk,
        "actions": list(actions),
        "commands": list(commands),
        "notes": notes,
        "gaps": list(gaps or []),
    }


def capability_registry(cwd: str = ".") -> dict:
    base = Path(cwd).resolve()
    runtime_dir = base / ".zero_os" / "runtime"
    snapshot_dir = base / ".zero_os" / "production" / "snapshots"
    apps_dir = base / "apps"
    github_dir = base / ".github"
    api_profiles = base / ".zero_os" / "connectors" / "api_profiles.json"
    api_profile_count = 0
    if api_profiles.exists():
        try:
            payload = json.loads(api_profiles.read_text(encoding="utf-8", errors="replace"))
            profiles = payload.get("profiles", {}) if isinstance(payload, dict) else {}
            if isinstance(profiles, dict):
                api_profile_count = len([name for name in profiles if str(name).strip()])
        except Exception:
            api_profile_count = 0

    return {
        "local_files": _tool(
            "Workspace files",
            enabled=base.exists(),
            ready=(base / "src").exists() or (base / "README.md").exists(),
            active=(base / "src").exists(),
            risk="medium",
            actions=["read", "write", "merge", "inspect"],
            commands=["show files", "list files", "merge files smart", "filesystem status"],
            notes="Primary lane for reading and editing the local Zero OS workspace.",
            gaps=[] if (base / "src").exists() else ["workspace source tree is not initialized"],
        ),
        "web_lookup": _tool(
            "Web lookup",
            enabled=True,
            ready=True,
            active=True,
            risk="medium",
            actions=["search", "fetch", "validate"],
            commands=["fetch <url>", "open <url>", "inspect page <url>"],
            notes="Verifies and fetches external pages before stronger browser actions.",
        ),
        "shell": _tool(
            "Shell execution",
            enabled=True,
            ready=True,
            active=True,
            risk="high",
            actions=["run", "inspect"],
            commands=["whoami", "date", "time", "shell run <command>"],
            notes="Unified terminal and PowerShell execution path.",
        ),
        "browser_automation": _tool(
            "Browser automation",
            enabled=True,
            ready=True,
            active=runtime_dir.exists(),
            risk="high",
            actions=["open", "inspect", "click", "input"],
            commands=[
                "zero ai browser status",
                "zero ai workflow browser open url=<url>",
                "zero ai workflow browser act url=<url> action=<open|inspect|click|input>",
            ],
            notes="Typed browser workflows are safer than raw browser actions and can be approval-gated.",
            gaps=[] if runtime_dir.exists() else ["browser workflows have no runtime evidence yet"],
        ),
        "system_runtime": _tool(
            "Runtime control plane",
            enabled=True,
            ready=(base / "src" / "main.py").exists(),
            active=(runtime_dir / "phase_runtime_status.json").exists(),
            risk="medium",
            actions=["status", "run", "repair", "observe", "govern"],
            commands=[
                "zero ai runtime status",
                "zero ai runtime run",
                "zero ai runtime loop status",
                "zero ai control workflows status",
                "zero ai observe",
            ],
            notes="Main orchestration, continuity, and inspection surface for Zero AI.",
            gaps=[] if (runtime_dir / "phase_runtime_status.json").exists() else ["runtime baseline has not been created yet"],
        ),
        "recovery": _tool(
            "Recovery and snapshots",
            enabled=True,
            ready=True,
            active=snapshot_dir.exists(),
            risk="high",
            actions=["backup", "restore", "recover", "rollback"],
            commands=["zero ai workflow recover", "snapshot create", "snapshot list", "snapshot restore"],
            notes="Safe rollback lane for bounded recovery and restore actions.",
            gaps=[] if snapshot_dir.exists() else ["no baseline recovery snapshot exists"],
        ),
        "github_ops": _tool(
            "GitHub operations",
            enabled=True,
            ready=github_dir.exists(),
            active=(github_dir / "workflows").exists(),
            risk="medium",
            actions=["connect", "read", "plan", "reply"],
            commands=["github status", "github repo connect <owner/repo>", "github issue plan <owner/repo> <number>"],
            notes="Issue and pull request intake, planning, and draft-reply helpers.",
            gaps=[] if github_dir.exists() else ["GitHub repo wiring is not present in this workspace"],
        ),
        "native_store": _tool(
            "Native store",
            enabled=True,
            ready=apps_dir.exists() or (base / "native_ui").exists(),
            active=any(apps_dir.iterdir()) if apps_dir.exists() else False,
            risk="high",
            actions=["install", "upgrade", "rollback", "release"],
            commands=["native store status", "zero ai workflow install app=<name>", "native store publish"],
            notes="App package install and release surface with approval or canary controls.",
            gaps=[] if (apps_dir.exists() and any(apps_dir.iterdir())) else ["no app packages are registered for autonomous install"],
        ),
        "api_profiles": _tool(
            "API profiles",
            enabled=True,
            ready=True,
            active=api_profile_count > 0,
            risk="medium",
            actions=["configure", "request", "workflow"],
            commands=["zero ai api profile status", "zero ai api profile set name=<name> base=<url>", "api workflow <profile> paths <p1,p2>"],
            notes="Reusable outbound API connectors for typed external integrations.",
            gaps=[] if api_profile_count > 0 else ["no reusable API profile has been configured"],
        ),
    }


def registry_status(cwd: str = ".") -> dict:
    data = capability_registry(cwd)
    path = _runtime_dir(cwd) / "tool_registry_status.json"
    missing_tools = [
        {"tool": key, "gaps": list(item.get("gaps", []))}
        for key, item in data.items()
        if item.get("gaps")
    ]
    highest_value_steps: list[str] = []
    if not data["system_runtime"]["active"]:
        highest_value_steps.append("Run `zero ai runtime run` to create a live runtime baseline before widening autonomy.")
    if not data["recovery"]["active"]:
        highest_value_steps.append("Create a baseline recovery snapshot so Zero AI can restore from a known-good point.")
    if not data["native_store"]["active"]:
        highest_value_steps.append("Publish or register at least one app package so the install workflow has a real target.")
    if not data["api_profiles"]["active"]:
        highest_value_steps.append("Configure at least one API profile so external services can run through typed connectors.")

    status = {
        "ok": True,
        "time_utc": _utc_now(),
        "path": str(path),
        "tools": data,
        "summary": {
            "tool_count": len(data),
            "enabled_count": sum(1 for item in data.values() if item.get("enabled")),
            "ready_count": sum(1 for item in data.values() if item.get("ready")),
            "active_count": sum(1 for item in data.values() if item.get("active")),
            "missing_tool_count": len(missing_tools),
        },
        "missing_tools": missing_tools,
        "highest_value_steps": highest_value_steps,
    }
    _save(path, status)
    return status
