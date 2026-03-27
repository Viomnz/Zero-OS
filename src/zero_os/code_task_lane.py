from __future__ import annotations

import subprocess
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

from zero_os.code_workbench import code_workbench_status


def _workspace_root(cwd: str) -> Path:
    return Path(cwd).resolve()


def parse_code_instruction(request: str) -> dict[str, Any]:
    text = str(request or "").strip()
    import re

    patterns = (
        r'replace\s+"([^"]+)"\s+with\s+"([^"]+)"',
        r"replace\s+'([^']+)'\s+with\s+'([^']+)'",
        r"replace\s+old=(.+?)\s+new=(.+?)(?:\s+(?:in|on)\s+|$)",
    )
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if not match:
            continue
        return {
            "ok": True,
            "operation": "replace",
            "old": str(match.group(1)),
            "new": str(match.group(2)),
            "parse_confidence": 1.0 if pattern != patterns[-1] else 0.85,
        }
    return {
        "ok": False,
        "operation": "",
        "old": "",
        "new": "",
        "parse_confidence": 0.0,
        "reason": "replace_instruction_missing",
    }


def _candidate_files(target: dict[str, Any]) -> tuple[list[str], list[dict[str, Any]]]:
    files = [str(item).strip() for item in list(target.get("files", [])) if str(item).strip()]
    file_ranges = [dict(item) for item in list(target.get("file_ranges", [])) if dict(item).get("path")]
    return files, file_ranges


def _read_existing_files(cwd: str, relative_files: list[str]) -> dict[str, str]:
    workspace = _workspace_root(cwd)
    contents: dict[str, str] = {}
    for relative_path in relative_files:
        contents[relative_path] = (workspace / relative_path).read_text(encoding="utf-8")
    return contents


def _restore_files(cwd: str, originals: dict[str, str]) -> None:
    workspace = _workspace_root(cwd)
    for relative_path, content in originals.items():
        (workspace / relative_path).write_text(content, encoding="utf-8")


def _apply_replace(content: str, old: str, new: str, *, replace_all: bool) -> tuple[str, int]:
    count = content.count(old)
    if count <= 0:
        return content, 0
    if replace_all:
        return content.replace(old, new), count
    return content.replace(old, new, 1), 1


def _apply_replace_within_range(content: str, old: str, new: str, file_range: dict[str, Any], *, replace_all: bool) -> tuple[str, int]:
    start = max(1, int(file_range.get("start_line", 1) or 1))
    end = max(start, int(file_range.get("end_line", start) or start))
    lines = content.splitlines(keepends=True)
    if not lines:
        return content, 0
    prefix = "".join(lines[: start - 1])
    body = "".join(lines[start - 1 : end])
    suffix = "".join(lines[end:])
    updated_body, replaced = _apply_replace(body, old, new, replace_all=replace_all)
    return prefix + updated_body + suffix, replaced


def _apply_candidate(cwd: str, target: dict[str, Any], instruction: dict[str, Any], *, replace_all: bool) -> dict[str, Any]:
    files, file_ranges = _candidate_files(target)
    workbench = code_workbench_status(
        cwd,
        requested_files=files,
        file_ranges=file_ranges,
        requested_mutation=True,
        request_text=str(target.get("request", "")),
    )
    if not bool(workbench.get("scope_ready", False)):
        return {"ok": False, "reason": "code_scope_not_ready", "workbench": workbench}
    in_scope_files = list(workbench.get("in_scope_files", []))
    originals = _read_existing_files(cwd, in_scope_files)
    workspace = _workspace_root(cwd)
    total_replacements = 0
    changed_files: list[str] = []
    range_map = {str(item.get("path", "")).strip(): dict(item) for item in file_ranges if str(item.get("path", "")).strip()}
    try:
        for relative_path in in_scope_files:
            absolute = workspace / relative_path
            content = originals[relative_path]
            file_range = range_map.get(relative_path)
            if file_range:
                updated, replaced = _apply_replace_within_range(
                    content,
                    str(instruction.get("old", "")),
                    str(instruction.get("new", "")),
                    file_range,
                    replace_all=replace_all,
                )
            else:
                updated, replaced = _apply_replace(
                    content,
                    str(instruction.get("old", "")),
                    str(instruction.get("new", "")),
                    replace_all=replace_all,
                )
            if replaced <= 0:
                continue
            absolute.write_text(updated, encoding="utf-8")
            total_replacements += replaced
            changed_files.append(relative_path)
        if total_replacements <= 0:
            _restore_files(cwd, originals)
            return {"ok": False, "reason": "replacement_not_found", "workbench": workbench}
        verification = run_code_verification(cwd, workbench, changed_files)
        if not bool(verification.get("ok", False)):
            _restore_files(cwd, originals)
            return {
                "ok": False,
                "reason": "verification_failed",
                "workbench": workbench,
                "verification": verification,
                "changed_files": changed_files,
            }
        return {
            "ok": True,
            "workbench": workbench,
            "verification": verification,
            "changed_files": changed_files,
            "replacement_count": total_replacements,
        }
    except Exception:
        _restore_files(cwd, originals)
        raise


def run_code_verification(cwd: str, workbench: dict[str, Any], changed_files: list[str]) -> dict[str, Any]:
    workspace = _workspace_root(cwd)
    compile_targets = [
        relative_path
        for relative_path in list(workbench.get("compile_targets", []))
        if relative_path in changed_files
    ]
    test_targets = list(workbench.get("focused_test_targets", []))
    compile_result = {"ok": True, "attempted": False, "targets": compile_targets, "stdout": "", "stderr": ""}
    if compile_targets:
        run = subprocess.run(
            [sys.executable, "-m", "py_compile", *compile_targets],
            cwd=str(workspace),
            capture_output=True,
            text=True,
            check=False,
        )
        compile_result = {
            "ok": run.returncode == 0,
            "attempted": True,
            "targets": compile_targets,
            "stdout": run.stdout,
            "stderr": run.stderr,
            "returncode": int(run.returncode),
        }
        if run.returncode != 0:
            return {"ok": False, "compile": compile_result, "tests": {"ok": False, "attempted": False, "targets": []}}

    test_result = {"ok": True, "attempted": False, "targets": test_targets, "stdout": "", "stderr": ""}
    if test_targets:
        run = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", *test_targets],
            cwd=str(workspace),
            capture_output=True,
            text=True,
            check=False,
        )
        test_result = {
            "ok": run.returncode == 0,
            "attempted": True,
            "targets": test_targets,
            "stdout": run.stdout,
            "stderr": run.stderr,
            "returncode": int(run.returncode),
        }
    return {"ok": bool(compile_result.get("ok", False)) and bool(test_result.get("ok", False)), "compile": compile_result, "tests": test_result}


def run_code_task(cwd: str, target: dict[str, Any]) -> dict[str, Any]:
    payload = dict(target or {})
    instruction = dict(payload.get("instruction") or {})
    if not instruction:
        instruction = parse_code_instruction(str(payload.get("request", "")))
    if not bool(instruction.get("ok", False)) or str(instruction.get("operation", "")) != "replace":
        workbench = code_workbench_status(
            cwd,
            requested_files=list(payload.get("files", [])),
            file_ranges=list(payload.get("file_ranges", [])),
            requested_mutation=True,
            request_text=str(payload.get("request", "")),
        )
        return {"ok": False, "reason": "code_instruction_missing", "instruction": instruction, "workbench": workbench}

    candidates = (
        {"id": "replace_first", "replace_all": False},
        {"id": "replace_all", "replace_all": True},
    )
    attempted: list[dict[str, Any]] = []
    for candidate in candidates:
        result = _apply_candidate(cwd, payload, instruction, replace_all=bool(candidate["replace_all"]))
        attempted.append(
            {
                "id": candidate["id"],
                "ok": bool(result.get("ok", False)),
                "reason": str(result.get("reason", "")),
                "replacement_count": int(result.get("replacement_count", 0) or 0),
                "changed_files": list(result.get("changed_files", [])),
            }
        )
        if bool(result.get("ok", False)):
            return {
                "ok": True,
                "candidate": candidate["id"],
                "instruction": instruction,
                "changed_files": list(result.get("changed_files", [])),
                "replacement_count": int(result.get("replacement_count", 0) or 0),
                "verification": dict(result.get("verification") or {}),
                "workbench": dict(result.get("workbench") or {}),
                "attempted_candidates": attempted,
            }

    fallback_workbench = code_workbench_status(
        cwd,
        requested_files=list(payload.get("files", [])),
        file_ranges=list(payload.get("file_ranges", [])),
        requested_mutation=True,
        request_text=str(payload.get("request", "")),
    )
    last_attempt = attempted[-1] if attempted else {}
    return {
        "ok": False,
        "reason": str(last_attempt.get("reason", "code_candidate_failed")),
        "instruction": instruction,
        "workbench": fallback_workbench,
        "attempted_candidates": attempted,
    }
