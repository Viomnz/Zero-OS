from __future__ import annotations

from pathlib import Path
from typing import Any


ALLOWED_CODE_ROOTS = ("src", "tests", "ai_from_scratch", "native_ui")


def _workspace_root(cwd: str) -> Path:
    return Path(cwd).resolve()


def _as_path_token(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("path", "") or "").strip()
    return str(value or "").strip()


def _resolve_target_path(cwd: str, value: Any) -> tuple[Path | None, str]:
    token = _as_path_token(value)
    if not token:
        return None, ""
    path = Path(token)
    resolved = path if path.is_absolute() else (_workspace_root(cwd) / path)
    return resolved.resolve(), token


def _relative_path(cwd: str, path: Path) -> str:
    try:
        return path.relative_to(_workspace_root(cwd)).as_posix()
    except ValueError:
        return ""


def classify_code_targets(cwd: str, requested_files: list[Any] | None = None) -> dict[str, Any]:
    workspace = _workspace_root(cwd)
    requested = list(requested_files or [])
    rows: list[dict[str, Any]] = []
    in_scope_files: list[str] = []
    out_of_scope_files: list[str] = []
    existing_in_scope_files: list[str] = []
    missing_in_scope_files: list[str] = []

    for raw in requested:
        resolved, token = _resolve_target_path(cwd, raw)
        if resolved is None:
            continue
        relative = _relative_path(cwd, resolved)
        in_workspace = bool(relative)
        root_name = relative.split("/", 1)[0] if relative else ""
        in_scope = in_workspace and root_name in ALLOWED_CODE_ROOTS
        exists = resolved.exists()
        row = {
            "requested": token,
            "resolved": str(resolved),
            "relative_path": relative,
            "in_workspace": in_workspace,
            "root": root_name,
            "in_scope": in_scope,
            "exists": exists,
        }
        rows.append(row)
        if not in_scope:
            out_of_scope_files.append(token or str(resolved))
            continue
        in_scope_files.append(relative)
        if exists:
            existing_in_scope_files.append(relative)
        else:
            missing_in_scope_files.append(relative)

    requested_count = len(rows)
    out_of_scope_count = len(out_of_scope_files)
    existing_in_scope_count = len(existing_in_scope_files)
    missing_in_scope_count = len(missing_in_scope_files)
    scope_ready = requested_count == 0 or (out_of_scope_count == 0 and missing_in_scope_count == 0 and existing_in_scope_count > 0)

    return {
        "ok": True,
        "workspace_root": str(workspace),
        "allowed_roots": list(ALLOWED_CODE_ROOTS),
        "requested_files": list(requested),
        "requested_count": requested_count,
        "scope_ready": scope_ready,
        "target_rows": rows,
        "in_scope_files": in_scope_files,
        "in_scope_count": len(in_scope_files),
        "existing_in_scope_files": existing_in_scope_files,
        "existing_in_scope_count": existing_in_scope_count,
        "missing_in_scope_files": missing_in_scope_files,
        "missing_in_scope_count": missing_in_scope_count,
        "out_of_scope_files": out_of_scope_files,
        "out_of_scope_count": out_of_scope_count,
    }

