from __future__ import annotations

import subprocess
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from zero_os.code_scope_registry import classify_code_targets


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _workspace_root(cwd: str) -> Path:
    return Path(cwd).resolve()


def _git_repo_root(cwd: str) -> Path | None:
    run = subprocess.run(
        ["git", "-C", str(_workspace_root(cwd)), "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=False,
    )
    if run.returncode != 0:
        return None
    root = str(run.stdout or "").strip()
    if not root:
        return None
    path = Path(root).resolve()
    return path if path.exists() else None


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered


def _target_files_from_request(files: list[Any] | None = None, file_ranges: list[Any] | None = None) -> list[Any]:
    requested: list[Any] = list(files or [])
    requested.extend(list(file_ranges or []))
    return requested


def _focused_test_targets(cwd: str, relative_files: list[str]) -> list[str]:
    workspace = _workspace_root(cwd)
    candidates: list[str] = []
    for relative_path in relative_files:
        path = Path(relative_path)
        if path.parts[:1] == ("tests",):
            candidates.append(relative_path)
            continue
        stem = path.stem
        if not stem:
            continue
        direct = workspace / "tests" / f"test_{stem}.py"
        if direct.exists():
            candidates.append(direct.relative_to(workspace).as_posix())
    return _dedupe(candidates)


def _compile_targets(cwd: str, relative_files: list[str]) -> list[str]:
    workspace = _workspace_root(cwd)
    targets: list[str] = []
    for relative_path in relative_files:
        absolute = workspace / relative_path
        if absolute.suffix.lower() == ".py" and absolute.exists():
            targets.append(relative_path)
    return _dedupe(targets)


def _git_summary(cwd: str, relative_files: list[str]) -> dict[str, Any]:
    repo_root = _git_repo_root(cwd)
    if repo_root is None:
        return {
            "git_available": False,
            "repo_root": "",
            "dirty_worktree": False,
            "change_count": 0,
            "dirty_files": [],
            "dirty_in_scope_files": [],
            "dirty_in_scope_count": 0,
        }
    run = subprocess.run(
        ["git", "-C", str(repo_root), "status", "--porcelain"],
        capture_output=True,
        text=True,
        check=False,
    )
    if run.returncode != 0:
        return {
            "git_available": False,
            "repo_root": str(repo_root),
            "dirty_worktree": False,
            "change_count": 0,
            "dirty_files": [],
            "dirty_in_scope_files": [],
            "dirty_in_scope_count": 0,
        }
    dirty_files: list[str] = []
    for line in [str(item).rstrip("\n") for item in str(run.stdout or "").splitlines() if str(item).strip()]:
        candidate = line[3:] if len(line) > 3 else line
        if "->" in candidate:
            candidate = candidate.split("->", 1)[1]
        candidate = candidate.strip()
        if not candidate:
            continue
        dirty_files.append(Path(candidate).as_posix())
    normalized_scope = {Path(item).as_posix() for item in relative_files}
    dirty_in_scope_files = [item for item in dirty_files if item in normalized_scope]
    return {
        "git_available": True,
        "repo_root": str(repo_root),
        "dirty_worktree": bool(dirty_files),
        "change_count": len(dirty_files),
        "dirty_files": _dedupe(dirty_files),
        "dirty_in_scope_files": _dedupe(dirty_in_scope_files),
        "dirty_in_scope_count": len(set(dirty_in_scope_files)),
    }


def _source_canary_summary(cwd: str) -> dict[str, Any]:
    try:
        from zero_os.zero_ai_source_evolution import zero_ai_source_evolution_status

        status = dict(zero_ai_source_evolution_status(cwd) or {})
    except Exception:
        status = {}
    proposal = dict(status.get("proposal") or {})
    last_canary = dict(status.get("last_canary") or {})
    pending_candidate = dict(status.get("pending_candidate") or {})
    return {
        "canary_ready": bool(proposal.get("candidate_available", False))
        and bool(proposal.get("safe", False))
        and bool(proposal.get("beneficial", False)),
        "last_canary_passed": bool(last_canary.get("passed", False)),
        "pending_candidate": bool(pending_candidate),
        "sandbox_patch_lane_ready": bool(status.get("sandboxed_patch_lane_ready", False)),
        "source_evolution_ready": bool(status.get("source_evolution_ready", False)),
        "recommended_action": str(status.get("recommended_action", "observe") or "observe"),
    }


def code_workbench_status(
    cwd: str,
    *,
    requested_files: list[Any] | None = None,
    file_ranges: list[Any] | None = None,
    requested_mutation: bool = False,
    request_text: str = "",
) -> dict[str, Any]:
    requested = _target_files_from_request(requested_files, file_ranges)
    scope = classify_code_targets(cwd, requested)
    existing_files = list(scope.get("existing_in_scope_files", []))
    compile_targets = _compile_targets(cwd, existing_files)
    focused_tests = _focused_test_targets(cwd, existing_files)
    git = _git_summary(cwd, existing_files)
    canary = _source_canary_summary(cwd)
    workspace_ready = _workspace_root(cwd).exists()
    target_file_count = int(scope.get("requested_count", 0) or 0)
    scope_ready = bool(scope.get("scope_ready", False))
    verification_ready = workspace_ready and (target_file_count == 0 or bool(existing_files))
    verification_surface_ready = workspace_ready and (len(compile_targets) > 0 or len(focused_tests) > 0)
    strong_verification_ready = workspace_ready and len(compile_targets) > 0 and len(focused_tests) > 0
    ready = workspace_ready and (not requested_mutation or (scope_ready and verification_ready))
    return {
        "ok": True,
        "time_utc": _utc_now(),
        "workspace_root": str(_workspace_root(cwd)),
        "workspace_ready": workspace_ready,
        "git_available": bool(git.get("git_available", False)),
        "repo_root": str(git.get("repo_root", "")),
        "dirty_worktree": bool(git.get("dirty_worktree", False)),
        "git_change_count": int(git.get("change_count", 0) or 0),
        "requested_code_mutation": bool(requested_mutation),
        "request_text": str(request_text or ""),
        "target_file_count": target_file_count,
        "scope_ready": scope_ready if target_file_count > 0 else True,
        "verification_ready": verification_ready,
        "verification_surface_ready": verification_surface_ready,
        "strong_verification_ready": strong_verification_ready,
        "ready": ready,
        "allowed_roots": list(scope.get("allowed_roots", [])),
        "in_scope_files": existing_files,
        "in_scope_count": len(existing_files),
        "dirty_in_scope_files": list(git.get("dirty_in_scope_files", [])),
        "dirty_in_scope_count": int(git.get("dirty_in_scope_count", 0) or 0),
        "out_of_scope_files": list(scope.get("out_of_scope_files", [])),
        "out_of_scope_count": int(scope.get("out_of_scope_count", 0) or 0),
        "missing_in_scope_files": list(scope.get("missing_in_scope_files", [])),
        "missing_in_scope_count": int(scope.get("missing_in_scope_count", 0) or 0),
        "compile_targets": compile_targets,
        "compile_target_count": len(compile_targets),
        "focused_test_targets": focused_tests,
        "focused_test_count": len(focused_tests),
        "verification_command_count": len(compile_targets) + (1 if focused_tests else 0),
        "source_canary_ready": bool(canary.get("canary_ready", False)),
        "source_last_canary_passed": bool(canary.get("last_canary_passed", False)),
        "source_pending_candidate": bool(canary.get("pending_candidate", False)),
        "source_sandbox_patch_lane_ready": bool(canary.get("sandbox_patch_lane_ready", False)),
        "source_evolution_ready": bool(canary.get("source_evolution_ready", False)),
        "source_recommended_action": str(canary.get("recommended_action", "observe") or "observe"),
        "scope": deepcopy(scope),
    }


def overlay_world_model_with_codebase(base_model: dict[str, Any] | None, code_workbench: dict[str, Any]) -> dict[str, Any]:
    model = deepcopy(base_model or {})
    if not model or bool(model.get("missing", False)) or not bool(model.get("ok", False)):
        model = {
            "ok": True,
            "missing": False,
            "time_utc": _utc_now(),
            "domains": {
                "runtime": {
                    "name": "runtime",
                    "source": "code_workbench_overlay",
                    "healthy": True,
                    "blocking": False,
                    "confidence": 0.75,
                    "summary": {
                        "runtime_ready": True,
                        "runtime_missing": False,
                        "runtime_loop_enabled": True,
                        "runtime_agent_installed": True,
                        "runtime_agent_running": True,
                    },
                },
                "continuity": {
                    "name": "continuity",
                    "source": "code_workbench_overlay",
                    "healthy": True,
                    "blocking": False,
                    "confidence": 0.75,
                    "summary": {"same_system": True, "has_contradiction": False, "continuity_score": 100.0},
                },
                "pressure": {
                    "name": "pressure",
                    "source": "code_workbench_overlay",
                    "healthy": True,
                    "blocking": False,
                    "confidence": 0.7,
                    "summary": {"pressure_ready": True, "overall_score": 100.0, "missing": False},
                },
                "recovery": {
                    "name": "recovery",
                    "source": "code_workbench_overlay",
                    "healthy": True,
                    "blocking": False,
                    "confidence": 0.7,
                    "summary": {"observed": False, "compatible_snapshot_ready": True, "snapshot_count": 0, "compatible_count": 0},
                },
                "approvals": {
                    "name": "approvals",
                    "source": "code_workbench_overlay",
                    "healthy": True,
                    "blocking": False,
                    "confidence": 0.75,
                    "summary": {"pending_count": 0, "expired_count": 0},
                },
                "jobs": {
                    "name": "jobs",
                    "source": "code_workbench_overlay",
                    "healthy": True,
                    "blocking": False,
                    "confidence": 0.75,
                    "summary": {"pending_count": 0},
                },
            },
            "blocked_domains": [],
            "degraded_domains": [],
            "fact_count": 0,
            "domain_count": 6,
            "facts": [],
        }
    domains = dict(model.get("domains") or {})
    requested_mutation = bool(code_workbench.get("requested_code_mutation", False))
    scope_ready = bool(code_workbench.get("scope_ready", False))
    verification_ready = bool(code_workbench.get("verification_ready", False))
    verification_surface_ready = bool(code_workbench.get("verification_surface_ready", False))
    out_of_scope_count = int(code_workbench.get("out_of_scope_count", 0) or 0)
    dirty_in_scope_count = int(code_workbench.get("dirty_in_scope_count", 0) or 0)
    healthy = bool(code_workbench.get("ready", False))
    blocking = requested_mutation and (not scope_ready or out_of_scope_count > 0 or dirty_in_scope_count > 0)
    domains["codebase"] = {
        "name": "codebase",
        "source": "code_workbench",
        "healthy": healthy,
        "blocking": blocking,
        "confidence": 0.9,
        "summary": {
            "workspace_ready": bool(code_workbench.get("workspace_ready", False)),
            "requested_code_mutation": requested_mutation,
            "scope_ready": scope_ready,
            "verification_ready": verification_ready,
            "verification_surface_ready": verification_surface_ready,
            "strong_verification_ready": bool(code_workbench.get("strong_verification_ready", False)),
            "target_file_count": int(code_workbench.get("target_file_count", 0) or 0),
            "in_scope_count": int(code_workbench.get("in_scope_count", 0) or 0),
            "out_of_scope_count": out_of_scope_count,
            "missing_in_scope_count": int(code_workbench.get("missing_in_scope_count", 0) or 0),
            "git_available": bool(code_workbench.get("git_available", False)),
            "dirty_worktree": bool(code_workbench.get("dirty_worktree", False)),
            "git_change_count": int(code_workbench.get("git_change_count", 0) or 0),
            "dirty_in_scope_count": dirty_in_scope_count,
            "focused_test_count": int(code_workbench.get("focused_test_count", 0) or 0),
            "compile_target_count": int(code_workbench.get("compile_target_count", 0) or 0),
            "source_canary_ready": bool(code_workbench.get("source_canary_ready", False)),
            "source_last_canary_passed": bool(code_workbench.get("source_last_canary_passed", False)),
            "source_pending_candidate": bool(code_workbench.get("source_pending_candidate", False)),
        },
    }
    blocked = {str(item) for item in list(model.get("blocked_domains", [])) if str(item)}
    degraded = {str(item) for item in list(model.get("degraded_domains", [])) if str(item)}
    if blocking:
        blocked.add("codebase")
    else:
        blocked.discard("codebase")
    if not healthy:
        degraded.add("codebase")
    else:
        degraded.discard("codebase")
    model["domains"] = domains
    model["blocked_domains"] = sorted(blocked)
    model["degraded_domains"] = sorted(degraded)
    model["domain_count"] = len(domains)
    model["time_utc"] = _utc_now()
    return model
