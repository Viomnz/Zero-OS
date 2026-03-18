from __future__ import annotations

from pathlib import Path

from zero_os.autonomous_fix_gate import capture_health_snapshot
from zero_os.contradiction_engine import contradiction_engine_status
from zero_os.flow_monitor import flow_status
from zero_os.smart_workspace import workspace_status
from zero_os.subsystem_controller_registry import controller_registry_status
from zero_os.tool_capability_registry import registry_status


def collect_observations(cwd: str) -> dict:
    from zero_os.zero_ai_pressure_harness import pressure_harness_status

    base = Path(cwd).resolve()
    return {
        "ok": True,
        "health": capture_health_snapshot(cwd),
        "tool_registry": registry_status(cwd),
        "controller_registry": controller_registry_status(cwd),
        "contradiction_engine": contradiction_engine_status(cwd),
        "pressure_harness": pressure_harness_status(cwd),
        "flow_monitor": flow_status(cwd),
        "smart_workspace": workspace_status(cwd),
        "workspace": {
            "cwd": str(base),
            "readme_exists": (base / "README.md").exists(),
            "runtime_dir": (base / ".zero_os" / "runtime").exists(),
        },
    }
