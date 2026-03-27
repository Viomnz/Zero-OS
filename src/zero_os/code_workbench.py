from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from zero_os.code_scope_registry import classify_code_targets


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _workspace_root(cwd: str) -> Path:
    return Path(cwd).resolve()


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
    workspace_ready = _workspace_root(cwd).exists()
    target_file_count = int(scope.get("requested_count", 0) or 0)
    scope_ready = bool(scope.get("scope_ready", False))
    verification_ready = workspace_ready and (target_file_count == 0 or bool(existing_files))
    ready = workspace_ready and (not requested_mutation or (scope_ready and verification_ready))
    return {
        "ok": True,
        "time_utc": _utc_now(),
        "workspace_root": str(_workspace_root(cwd)),
        "workspace_ready": workspace_ready,
        "requested_code_mutation": bool(requested_mutation),
        "request_text": str(request_text or ""),
        "target_file_count": target_file_count,
        "scope_ready": scope_ready if target_file_count > 0 else True,
        "verification_ready": verification_ready,
        "ready": ready,
        "allowed_roots": list(scope.get("allowed_roots", [])),
        "in_scope_files": existing_files,
        "in_scope_count": len(existing_files),
        "out_of_scope_files": list(scope.get("out_of_scope_files", [])),
        "out_of_scope_count": int(scope.get("out_of_scope_count", 0) or 0),
        "missing_in_scope_files": list(scope.get("missing_in_scope_files", [])),
        "missing_in_scope_count": int(scope.get("missing_in_scope_count", 0) or 0),
        "compile_targets": compile_targets,
        "compile_target_count": len(compile_targets),
        "focused_test_targets": focused_tests,
        "focused_test_count": len(focused_tests),
        "verification_command_count": len(compile_targets) + (1 if focused_tests else 0),
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
    out_of_scope_count = int(code_workbench.get("out_of_scope_count", 0) or 0)
    healthy = bool(code_workbench.get("ready", False))
    blocking = requested_mutation and (not scope_ready or out_of_scope_count > 0)
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
            "target_file_count": int(code_workbench.get("target_file_count", 0) or 0),
            "in_scope_count": int(code_workbench.get("in_scope_count", 0) or 0),
            "out_of_scope_count": out_of_scope_count,
            "missing_in_scope_count": int(code_workbench.get("missing_in_scope_count", 0) or 0),
            "focused_test_count": int(code_workbench.get("focused_test_count", 0) or 0),
            "compile_target_count": int(code_workbench.get("compile_target_count", 0) or 0),
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
