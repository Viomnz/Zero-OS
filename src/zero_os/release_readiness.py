from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from zero_os.recovery import zero_ai_recovery_inventory
from zero_os.smart_workspace import workspace_status
from zero_os.world_class_readiness import world_class_readiness_status


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _assistant_dir(cwd: str) -> Path:
    path = Path(cwd).resolve() / ".zero_os" / "assistant"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _path(cwd: str) -> Path:
    return _assistant_dir(cwd) / "release_readiness.json"


def _save(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def release_readiness_status(cwd: str) -> dict[str, Any]:
    workspace = workspace_status(cwd)
    world_class = world_class_readiness_status(cwd)
    recovery = zero_ai_recovery_inventory(cwd)

    git = dict(workspace.get("git") or {})
    summary = dict(workspace.get("summary") or {})
    checks = {
        "git_clean": not bool(git.get("dirty", False)),
        "workspace_indexed": bool(summary.get("indexed", False)),
        "flow_clean": float(summary.get("flow_score", 0.0) or 0.0) >= 95.0 and int(summary.get("flow_issue_count", 0) or 0) == 0,
        "world_class_score_maxed": float(world_class.get("overall_score", 0.0) or 0.0) >= 100.0,
        "latest_compatible_snapshot_present": bool(recovery.get("latest_compatible_snapshot_id", "")),
    }
    ready = all(checks.values())
    blockers: list[str] = []
    if not checks["git_clean"]:
        blockers.append("dirty_worktree")
    if not checks["workspace_indexed"]:
        blockers.append("workspace_index_missing")
    if not checks["flow_clean"]:
        blockers.append("flow_not_clean")
    if not checks["world_class_score_maxed"]:
        blockers.append("world_class_readiness_not_maxed")
    if not checks["latest_compatible_snapshot_present"]:
        blockers.append("latest_compatible_snapshot_missing")

    highest_value_steps: list[str] = []
    if "dirty_worktree" in blockers:
        highest_value_steps.append("Reduce the git working tree to an intentional release set before calling Zero OS release-ready.")
    if "latest_compatible_snapshot_missing" in blockers:
        highest_value_steps.append("Create and validate a fresh compatible recovery snapshot so release state has a trusted rollback point.")
    if not highest_value_steps:
        highest_value_steps.append("Maintain the release baseline and keep pressure, flow, and recovery evidence green.")

    payload = {
        "ok": True,
        "time_utc": _utc_now(),
        "release_ready": ready,
        "checks": checks,
        "blockers": blockers,
        "workspace": {
            "git_dirty": bool(git.get("dirty", False)),
            "git_change_count": int(git.get("change_count", 0) or 0),
            "indexed": bool(summary.get("indexed", False)),
            "flow_score": float(summary.get("flow_score", 0.0) or 0.0),
            "flow_issue_count": int(summary.get("flow_issue_count", 0) or 0),
        },
        "world_class": {
            "overall_score": float(world_class.get("overall_score", 0.0) or 0.0),
            "world_class_now": bool(world_class.get("world_class_now", False)),
        },
        "recovery": {
            "snapshot_count": int(recovery.get("snapshot_count", 0) or 0),
            "latest_snapshot_id": str(recovery.get("latest_snapshot_id", "") or ""),
            "latest_compatible_snapshot_id": str(recovery.get("latest_compatible_snapshot_id", "") or ""),
            "compatible_count": int(recovery.get("compatible_count", 0) or 0),
        },
        "highest_value_steps": highest_value_steps,
        "path": str(_path(cwd)),
    }
    _save(_path(cwd), payload)
    return payload


def release_readiness_refresh(cwd: str) -> dict[str, Any]:
    return release_readiness_status(cwd)
