from __future__ import annotations

from pathlib import Path

from zero_os.autonomous_fix_gate import capture_health_snapshot
from zero_os.tool_capability_registry import capability_registry


def collect_observations(cwd: str) -> dict:
    base = Path(cwd).resolve()
    return {
        "ok": True,
        "health": capture_health_snapshot(cwd),
        "tool_registry": capability_registry(),
        "workspace": {
            "cwd": str(base),
            "readme_exists": (base / "README.md").exists(),
            "runtime_dir": (base / ".zero_os" / "runtime").exists(),
        },
    }
