from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _runtime(base: Path) -> Path:
    p = base / ".zero_os" / "runtime"
    p.mkdir(parents=True, exist_ok=True)
    return p


def run_smart_flow(cwd: str, workspace: str = "") -> dict:
    base = Path(cwd).resolve()
    ws = Path(workspace).resolve() if workspace else base
    runtime = _runtime(base)

    flow = {
        "time_utc": _utc_now(),
        "workspace_path": str(ws),
        "workspace_exists": ws.exists(),
        "project_detected": any((ws / marker).exists() for marker in [".git", "README.md", "src"]),
        "steps": [
            {"name": "workspace_detect", "ok": ws.exists()},
            {"name": "runtime_ready", "ok": True},
            {"name": "project_probe", "ok": any((ws / marker).exists() for marker in [".git", "README.md", "src"])},
        ],
        "next": [],
    }
    if not flow["workspace_exists"]:
        flow["next"].append("create_or_select_workspace")
    if flow["workspace_exists"] and not flow["project_detected"]:
        flow["next"].append("initialize_project_structure")
    if flow["workspace_exists"] and flow["project_detected"]:
        flow["next"].append("run_daemon_status")
        flow["next"].append("open_dashboard")

    (runtime / "workspace_state.json").write_text(json.dumps(flow, indent=2) + "\n", encoding="utf-8")
    return flow
