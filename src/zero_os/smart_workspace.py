from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from zero_os.flow_monitor import flow_status
from zero_os.large_code_index import index_status, index_workspace, list_workspaces, symbol_status


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _assistant_dir(cwd: str) -> Path:
    path = Path(cwd).resolve() / ".zero_os" / "assistant"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _status_path(cwd: str) -> Path:
    return _assistant_dir(cwd) / "smart_workspace.json"


def _save(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _top_level_inventory(base: Path) -> dict[str, Any]:
    entries = sorted(base.iterdir(), key=lambda item: (not item.is_dir(), item.name.lower()))
    visible = [item for item in entries if item.name not in {".zero_os", "__pycache__"}]
    directories = [item.name for item in visible if item.is_dir()]
    files = [item.name for item in visible if item.is_file()]
    return {
        "directory_count": len(directories),
        "file_count": len(files),
        "directories": directories[:12],
        "files": files[:12],
        "has_src": (base / "src").exists(),
        "has_tests": (base / "tests").exists(),
        "has_readme": any((base / name).exists() for name in ("README.md", "readme.md")),
        "has_git": _git_available(base),
    }


def _git_available(base: Path) -> bool:
    try:
        result = subprocess.run(
            ["git", "-C", str(base), "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
            check=False,
        )
    except Exception:
        return False
    return result.returncode == 0


def _git_status(base: Path) -> dict[str, Any]:
    if not _git_available(base):
        return {
            "available": False,
            "dirty": False,
            "branch": "",
            "repo_root": "",
            "change_count": 0,
            "modified_count": 0,
            "added_count": 0,
            "deleted_count": 0,
            "renamed_count": 0,
            "untracked_count": 0,
        }

    branch = ""
    repo_root = ""
    try:
        branch_result = subprocess.run(
            ["git", "-C", str(base), "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
            check=False,
        )
        if branch_result.returncode == 0:
            branch = branch_result.stdout.strip()
        root_result = subprocess.run(
            ["git", "-C", str(base), "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
            check=False,
        )
        if root_result.returncode == 0:
            repo_root = root_result.stdout.strip()
        status_result = subprocess.run(
            ["git", "-C", str(base), "status", "--porcelain"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15,
            check=False,
        )
    except Exception:
        return {
            "available": True,
            "dirty": False,
            "branch": branch,
            "repo_root": repo_root,
            "change_count": 0,
            "modified_count": 0,
            "added_count": 0,
            "deleted_count": 0,
            "renamed_count": 0,
            "untracked_count": 0,
            "status_error": True,
        }

    modified_count = 0
    added_count = 0
    deleted_count = 0
    renamed_count = 0
    untracked_count = 0
    lines = [line.rstrip("\n") for line in status_result.stdout.splitlines() if line.strip()]
    for line in lines:
        code = line[:2]
        if code == "??":
            untracked_count += 1
            continue
        if "M" in code:
            modified_count += 1
        if "A" in code:
            added_count += 1
        if "D" in code:
            deleted_count += 1
        if "R" in code:
            renamed_count += 1

    return {
        "available": True,
        "dirty": bool(lines),
        "branch": branch,
        "repo_root": repo_root,
        "change_count": len(lines),
        "modified_count": modified_count,
        "added_count": added_count,
        "deleted_count": deleted_count,
        "renamed_count": renamed_count,
        "untracked_count": untracked_count,
    }


def _highest_value_steps(indexed: bool, index_data: dict[str, Any], flow: dict[str, Any], git: dict[str, Any]) -> list[str]:
    steps: list[str] = []
    flow_summary = dict(flow.get("summary") or {})
    if not indexed:
        steps.append("Run `zero ai workspace refresh` to build a searchable smart workspace map.")
    else:
        changed = int(index_data.get("changed_files", 0) or 0)
        if changed > 0:
            steps.append(f"Review the {changed} workspace changes surfaced by the latest index before wider edits.")
        else:
            steps.append("Maintain the indexed workspace map so search, symbols, and file awareness stay current.")
    if not bool(flow_summary.get("source_scan_available", False)):
        steps.append("Run `zero ai flow scan` to attach contradiction, bug, error, and threat signals to the workspace map.")
    if bool(git.get("available", False)) and bool(git.get("dirty", False)):
        steps.append("Review the current git working tree before promoting larger workspace changes.")
    if not steps:
        steps.append("Maintain the smart workspace so Zero OS keeps a clean map of structure, changes, and risk.")
    return steps


def workspace_status(cwd: str, name: str = "main") -> dict[str, Any]:
    base = Path(cwd).resolve()
    workspaces = list_workspaces(cwd)
    index_data = index_status(cwd, name=name)
    symbols = symbol_status(cwd, name=name)
    flow = flow_status(cwd)
    git = _git_status(base)
    inventory = _top_level_inventory(base)
    indexed = bool(index_data.get("ok", False))
    search_ready = indexed and bool(symbols.get("ok", False))

    status = {
        "ok": True,
        "time_utc": _utc_now(),
        "path": str(_status_path(cwd)),
        "workspace": name,
        "active": base.exists(),
        "ready": True,
        "summary": {
            "indexed": indexed,
            "search_ready": search_ready,
            "file_count": int(index_data.get("file_count", 0) or 0),
            "text_file_count": int(index_data.get("text_file_count", 0) or 0),
            "changed_files": int(index_data.get("changed_files", 0) or 0),
            "symbol_file_count": int(symbols.get("symbol_file_count", 0) or 0),
            "symbol_count": int(symbols.get("symbol_count", 0) or 0),
            "git_available": bool(git.get("available", False)),
            "git_dirty": bool(git.get("dirty", False)),
            "git_change_count": int(git.get("change_count", 0) or 0),
            "flow_score": float((flow.get("summary") or {}).get("flow_score", 0.0) or 0.0),
            "flow_issue_count": int((flow.get("summary") or {}).get("issue_count", 0) or 0),
            "top_level_directory_count": int(inventory.get("directory_count", 0) or 0),
            "top_level_file_count": int(inventory.get("file_count", 0) or 0),
        },
        "checks": {
            "index_ready": indexed,
            "search_ready": search_ready,
            "git_clean": (not bool(git.get("dirty", False))) if bool(git.get("available", False)) else True,
            "flow_baseline_ready": bool((flow.get("summary") or {}).get("source_scan_available", False)),
        },
        "inventory": inventory,
        "git": git,
        "index": index_data,
        "symbols": symbols,
        "flow": {
            "summary": dict(flow.get("summary") or {}),
            "checks": dict(flow.get("checks") or {}),
        },
        "registered_workspaces": workspaces,
        "highest_value_steps": _highest_value_steps(indexed, index_data, flow, git),
    }
    _save(_status_path(cwd), status)
    return status


def workspace_refresh(
    cwd: str,
    name: str = "main",
    max_files: int = 50000,
    shard_size: int = 1000,
    incremental: bool = True,
) -> dict[str, Any]:
    index_result = index_workspace(cwd, name=name, max_files=max_files, shard_size=shard_size, incremental=incremental)
    status = workspace_status(cwd, name=name)
    status["index_refresh"] = index_result
    status["ok"] = bool(index_result.get("ok", False)) and bool(status.get("ok", False))
    _save(_status_path(cwd), status)
    return status
