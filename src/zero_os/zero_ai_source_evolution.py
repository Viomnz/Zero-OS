from __future__ import annotations

import difflib
import hashlib
import json
import re
import shutil
import subprocess
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _evolution_root(cwd: str) -> Path:
    path = Path(cwd).resolve() / ".zero_os" / "evolution" / "source"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _checkpoint_root(cwd: str) -> Path:
    path = _evolution_root(cwd) / "checkpoints"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _canary_workspace_root(cwd: str) -> Path:
    path = _evolution_root(cwd) / "canary_workspaces"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _review_root(cwd: str) -> Path:
    path = _evolution_root(cwd) / "reviews"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _state_path(cwd: str) -> Path:
    return _evolution_root(cwd) / "state.json"


def _history_path(cwd: str) -> Path:
    return _evolution_root(cwd) / "history.jsonl"


def _load_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return dict(default)
    try:
        payload = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return dict(default)
    if not isinstance(payload, dict):
        return dict(default)
    merged = dict(default)
    merged.update(payload)
    return merged


def _save_json(path: Path, payload: dict[str, Any]) -> None:
    payload["updated_utc"] = _utc_now()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _append_history(cwd: str, payload: dict[str, Any]) -> None:
    with _history_path(cwd).open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")


def _history_tail(cwd: str, limit: int = 10) -> list[dict[str, Any]]:
    path = _history_path(cwd)
    if not path.exists():
        return []
    rows = [line.strip() for line in path.read_text(encoding="utf-8", errors="replace").splitlines() if line.strip()]
    out: list[dict[str, Any]] = []
    for row in rows[-limit:]:
        try:
            payload = json.loads(row)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            out.append(payload)
    return out


def _parse_utc(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _target_spec_definitions() -> list[dict[str, Any]]:
    return [
        {
            "key": "runtime_loop_source_default",
            "label": "Phase runtime loop default",
            "relative_path": "src/zero_os/phase_runtime.py",
            "pattern": r'(def _runtime_loop_default\(\) -> dict:\s+return \{\s+"enabled": False,\s+"interval_seconds": )(\d+)',
            "target_key": "runtime_loop_interval_seconds",
            "test_hint": "tests.test_phase_runtime",
            "scope": "src/zero_os/phase_runtime.py:_runtime_loop_default.interval_seconds",
            "lane_kind": "profile_alignment",
        },
        {
            "key": "autonomy_loop_source_default",
            "label": "Autonomy loop default",
            "relative_path": "src/zero_os/zero_ai_autonomy.py",
            "pattern": r'(def _loop_state_default\(\) -> dict:\s+return \{\s+"enabled": False,\s+"interval_seconds": )(\d+)',
            "target_key": "autonomy_loop_interval_seconds",
            "test_hint": "tests.test_zero_ai_autonomy",
            "scope": "src/zero_os/zero_ai_autonomy.py:_loop_state_default.interval_seconds",
            "lane_kind": "profile_alignment",
        },
        {
            "key": "self_repair_minimum_readiness_floor_source_default",
            "label": "Self-repair readiness floor default",
            "relative_path": "src/zero_os/zero_ai_control_workflows.py",
            "pattern": r'("self_repair": \{\s+"enabled": True,\s+"mode": "canary_backed",\s+"minimum_readiness_floor": )(\d+)',
            "target_key": "self_repair_minimum_readiness_floor",
            "test_hint": "tests.test_zero_ai_control_workflows",
            "scope": "src/zero_os/zero_ai_control_workflows.py:_lane_defaults.self_repair.minimum_readiness_floor",
            "lane_kind": "sandbox_patch",
        },
        {
            "key": "continuity_governance_interval_source_default",
            "label": "Continuity governance default interval",
            "relative_path": "src/zero_os/self_continuity.py",
            "pattern": r'(def _governance_default\(\) -> dict\[str, Any\]:\s+return \{\s+"enabled": False,\s+"interval_seconds": )(\d+)',
            "target_key": "continuity_governance_interval_seconds",
            "test_hint": "tests.test_self_continuity",
            "scope": "src/zero_os/self_continuity.py:_governance_default.interval_seconds",
            "lane_kind": "sandbox_patch",
        },
        {
            "key": "triad_ops_interval_source_default",
            "label": "Triad ops default interval",
            "relative_path": "src/zero_os/triad_balance.py",
            "pattern": r'(def triad_ops_status\(cwd: str\) -> dict:\s+default = \{\s+"enabled": False,\s+"interval_seconds": )(\d+)',
            "target_key": "triad_ops_interval_seconds",
            "test_hint": "tests.test_triad_balance",
            "scope": "src/zero_os/triad_balance.py:triad_ops_status.default.interval_seconds",
            "lane_kind": "sandbox_patch",
        },
        {
            "key": "antivirus_monitor_interval_source_default",
            "label": "Antivirus monitor default interval",
            "relative_path": "src/zero_os/antivirus.py",
            "pattern": r'(def monitor_status\(cwd: str\) -> dict:\s+default = \{"enabled": False, "last_tick_utc": "", "last_scan_path": "\.", "interval_seconds": )(\d+)',
            "target_key": "antivirus_monitor_interval_seconds",
            "test_hint": "tests.test_antivirus_system",
            "scope": "src/zero_os/antivirus.py:monitor_status.default.interval_seconds",
            "lane_kind": "sandbox_patch",
        },
    ]


def _state_default() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "allowed_scopes": [str(item.get("scope", "")) for item in _target_spec_definitions()],
        "current_source_generation": 0,
        "promoted_count": 0,
        "rollback_count": 0,
        "auto_enabled": True,
        "min_auto_interval_seconds": 21600,
        "last_auto_run_utc": "",
        "next_auto_run_utc": "",
        "last_proposal": {},
        "last_simulation": {},
        "last_canary": {},
        "last_promotion": {},
        "last_rollback": {},
        "pending_candidate": {},
        "updated_utc": _utc_now(),
    }


def _load_state(cwd: str) -> dict[str, Any]:
    state = _load_json(_state_path(cwd), _state_default())
    default = _state_default()
    for key, value in default.items():
        state.setdefault(key, value)
    existing_scopes = [str(item) for item in state.get("allowed_scopes", [])]
    merged_scopes = list(existing_scopes)
    for scope in default.get("allowed_scopes", []):
        scope_text = str(scope)
        if scope_text not in merged_scopes:
            merged_scopes.append(scope_text)
    state["allowed_scopes"] = merged_scopes
    return state


def _save_state(cwd: str, state: dict[str, Any]) -> dict[str, Any]:
    _save_json(_state_path(cwd), state)
    return state


def _git_repo_root(cwd: str) -> Path | None:
    completed = subprocess.run(
        ["git", "-C", str(Path(cwd).resolve()), "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed.returncode != 0:
        return None
    root = completed.stdout.strip()
    if not root:
        return None
    path = Path(root).resolve()
    if not path.exists():
        return None
    return path


def _target_specs(cwd: str) -> list[dict[str, Any]]:
    repo_root = Path(cwd).resolve()
    specs: list[dict[str, Any]] = []
    for definition in _target_spec_definitions():
        spec = dict(definition)
        spec["path"] = str(repo_root / Path(str(spec["relative_path"])))
        specs.append(spec)
    return specs


def _candidate_id(target_profile: dict[str, Any], mutations: list[dict[str, Any]]) -> str:
    payload = {
        "profile": target_profile,
        "mutations": [
            {
                "key": str(item.get("key", "")),
                "path": str(item.get("path", "")),
                "from": item.get("from"),
                "to": item.get("to"),
            }
            for item in mutations
        ],
    }
    encoded = json.dumps(payload, sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:10]


def _extract_current_value(content: str, pattern: str) -> int | None:
    match = re.search(pattern, content, flags=re.S)
    if not match:
        return None
    try:
        return int(match.group(2))
    except (IndexError, TypeError, ValueError):
        return None


def _replace_value(content: str, pattern: str, new_value: int) -> tuple[str, bool]:
    def repl(match: re.Match[str]) -> str:
        return f"{match.group(1)}{int(new_value)}"

    updated, count = re.subn(pattern, repl, content, count=1, flags=re.S)
    return updated, count == 1


def _line_number_for_pattern(content: str, pattern: str) -> int | None:
    match = re.search(pattern, content, flags=re.S)
    if not match:
        return None
    return content[: match.start(2)].count("\n") + 1


def _line_text(content: str, line_number: int | None) -> str:
    if line_number is None:
        return ""
    lines = content.splitlines()
    index = max(0, int(line_number) - 1)
    if index >= len(lines):
        return ""
    return lines[index].strip()


def _auto_due(state: dict[str, Any]) -> bool:
    if not bool(state.get("auto_enabled", True)):
        return False
    next_run = _parse_utc(str(state.get("next_auto_run_utc", "")))
    if next_run is None:
        return True
    return datetime.now(timezone.utc) >= next_run


def _schedule_next_auto_run(state: dict[str, Any]) -> None:
    interval = max(900, min(86400, int(state.get("min_auto_interval_seconds", 21600) or 21600)))
    state["last_auto_run_utc"] = _utc_now()
    state["next_auto_run_utc"] = (datetime.now(timezone.utc) + timedelta(seconds=interval)).isoformat()


def _source_ready(evolution_status: dict[str, Any]) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if not bool(evolution_status.get("ok", False)):
        reasons.append("bounded evolution status is unavailable")
    if int(evolution_status.get("current_generation", 0) or 0) < 1:
        reasons.append("bounded evolution has not promoted a stable runtime profile yet")
    if not bool(evolution_status.get("self_evolution_ready", False)):
        reasons.append("bounded evolution safety preconditions are not satisfied")
    if float((evolution_status.get("fitness") or {}).get("fitness_score", 0.0) or 0.0) < 95.0:
        reasons.append("bounded evolution fitness is not high enough to align source defaults")
    pending = dict(evolution_status.get("pending_candidate") or {})
    if pending:
        reasons.append("bounded evolution still has a pending candidate")
    recommended = str(evolution_status.get("recommended_action", "observe"))
    if recommended not in {"observe", "promote"}:
        reasons.append(f"bounded evolution should settle before source evolution ({recommended})")
    return (len(reasons) == 0, reasons)


def _derive_self_repair_floor(cwd: str) -> int:
    runtime_status_path = Path(cwd).resolve() / ".zero_os" / "runtime" / "phase_runtime_status.json"
    runtime_status = _load_json(runtime_status_path, {"runtime_score": 0.0, "runtime_ready": False})
    runtime_score = float(runtime_status.get("runtime_score", 0.0) or 0.0)
    if runtime_score <= 0:
        return 0
    return max(60, min(90, int(runtime_score) - 10))


def _clamp_interval_target(value: int, minimum: int = 60, maximum: int = 3600) -> int:
    return max(minimum, min(maximum, int(value)))


def _derive_continuity_governance_interval(cwd: str) -> int:
    from zero_os.self_continuity import zero_ai_continuity_governance_auto_status

    governance = zero_ai_continuity_governance_auto_status(cwd)
    current_enabled = bool(governance.get("current_enabled", False))
    recommended_enabled = bool(governance.get("recommended_enabled", False))
    if not current_enabled and not recommended_enabled:
        return 0
    if current_enabled:
        return _clamp_interval_target(int(governance.get("current_interval_seconds", 0) or 0))
    return _clamp_interval_target(int(governance.get("recommended_interval_seconds", 0) or 0))


def _derive_triad_ops_interval(cwd: str) -> int:
    from zero_os.triad_balance import triad_ops_status

    triad = triad_ops_status(cwd)
    if not bool(triad.get("enabled", False)):
        return 0
    return _clamp_interval_target(int(triad.get("interval_seconds", 0) or 0))


def _derive_antivirus_monitor_interval(cwd: str) -> int:
    from zero_os.antivirus import monitor_status

    monitor = monitor_status(cwd)
    if not bool(monitor.get("enabled", False)):
        return 0
    return _clamp_interval_target(int(monitor.get("interval_seconds", 0) or 0))


def _target_profile_from_live(cwd: str, evolution_status: dict[str, Any]) -> dict[str, int]:
    current_profile = dict(evolution_status.get("current_profile") or {})
    return {
        "runtime_loop_interval_seconds": int(current_profile.get("runtime_loop_interval_seconds", 0) or 0),
        "autonomy_loop_interval_seconds": int(current_profile.get("autonomy_loop_interval_seconds", 0) or 0),
        "self_repair_minimum_readiness_floor": _derive_self_repair_floor(cwd),
        "continuity_governance_interval_seconds": _derive_continuity_governance_interval(cwd),
        "triad_ops_interval_seconds": _derive_triad_ops_interval(cwd),
        "antivirus_monitor_interval_seconds": _derive_antivirus_monitor_interval(cwd),
    }


def _verification_test_targets(cwd: str, mutations: list[dict[str, Any]]) -> list[str]:
    repo_root = Path(cwd).resolve()
    modules = ["tests.test_zero_ai_evolution", "tests.test_zero_ai_source_evolution"]
    for mutation in mutations:
        hint = str(mutation.get("test_hint", "")).strip()
        if hint and hint not in modules:
            modules.append(hint)
    existing: list[str] = []
    for module in modules:
        module_path = repo_root / Path(*module.split(".")).with_suffix(".py")
        if module_path.exists():
            existing.append(module)
    return existing


def _verification_plan(cwd: str, mutations: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "py_compile": [str(item.get("path", "")) for item in mutations if str(item.get("path", "")).strip()],
        "tests": _verification_test_targets(cwd, mutations),
    }


def _proposal_from_live(cwd: str) -> dict[str, Any]:
    from zero_os.zero_ai_evolution import zero_ai_evolution_status

    evolution_status = zero_ai_evolution_status(cwd)
    ready, ready_reasons = _source_ready(evolution_status)
    target_profile = _target_profile_from_live(cwd, evolution_status)

    mutations: list[dict[str, Any]] = []
    missing_files: list[str] = []
    specs = _target_specs(cwd)
    spec_map = {str(item.get("key", "")): item for item in specs}
    for spec in specs:
        path = Path(spec["path"])
        if not path.exists():
            missing_files.append(spec["relative_path"])
            continue
        content = path.read_text(encoding="utf-8", errors="replace")
        current_value = _extract_current_value(content, str(spec["pattern"]))
        target_value = int(target_profile.get(str(spec["target_key"]), 0) or 0)
        if current_value is None:
            missing_files.append(spec["relative_path"])
            continue
        if target_value <= 0:
            continue
        if current_value != target_value:
            mutations.append(
                {
                    "key": spec["key"],
                    "label": spec["label"],
                    "path": spec["relative_path"],
                    "from": current_value,
                    "to": target_value,
                    "test_hint": spec["test_hint"],
                    "scope": spec["scope"],
                    "lane_kind": spec["lane_kind"],
                }
            )

    beneficial = bool(mutations)
    candidate_id = _candidate_id(target_profile, mutations)
    predicted_gain = round(len(mutations) * 3.5, 2)
    sandbox_specs = [item for item in specs if str(item.get("lane_kind", "")) == "sandbox_patch"]
    sandbox_scope_count = len(sandbox_specs)
    missing_sandbox_files = [item["relative_path"] for item in sandbox_specs if item["relative_path"] in missing_files]
    sandbox_patch_targets = [
        item for item in mutations if str(spec_map.get(str(item.get("key", "")), {}).get("lane_kind", "")) == "sandbox_patch"
    ]
    sandbox_patch_lane_ready = ready and sandbox_scope_count > 0 and not missing_sandbox_files
    expanded_sandbox_patch_lane = sandbox_patch_lane_ready and sandbox_scope_count >= 3
    summary = "learned source defaults already match the promoted runtime profile"
    if missing_files:
        summary = "source evolution is blocked because one or more allowlisted source files are missing"
    elif mutations:
        summary = (
            "guarded source evolution candidate generated from the promoted runtime profile and expanded sandboxed non-identity patch lane"
            if expanded_sandbox_patch_lane
            else "guarded source evolution candidate generated from the promoted runtime profile and sandboxed non-identity patch lane"
        )
    if not ready:
        summary = "guarded source evolution is blocked until bounded evolution settles"

    verification_plan = _verification_plan(cwd, mutations)

    proposal = {
        "ok": True,
        "candidate_id": candidate_id,
        "time_utc": _utc_now(),
        "generated_by": "zero_ai",
        "upgrade_kind": "guarded_source_patch",
        "generation_mode": "auto_candidate",
        "candidate_available": bool(mutations),
        "beneficial": beneficial,
        "safe": ready and not missing_files,
        "blocked_reasons": ([] if ready else ready_reasons) + [f"missing allowlisted source file: {path}" for path in missing_files],
        "current_profile": target_profile,
        "mutations": mutations,
        "sandbox_patch_lane_ready": sandbox_patch_lane_ready,
        "sandbox_patch_targets": sandbox_patch_targets,
        "sandbox_patch_scope_count": sandbox_scope_count,
        "expanded_sandbox_patch_lane": expanded_sandbox_patch_lane,
        "predicted_gain": predicted_gain if beneficial else 0.0,
        "summary": summary,
        "verification_plan": verification_plan,
    }
    patch_review = _build_patch_review(cwd, proposal)
    proposal["patch_review"] = patch_review
    proposal["patch_review_path"] = str(patch_review.get("artifact_path", ""))
    proposal["patch_review_json_path"] = str(patch_review.get("artifact_json_path", ""))
    proposal["patch_review_summary"] = str(patch_review.get("summary", ""))
    proposal["patch_review_headlines"] = list(patch_review.get("change_headlines", []))
    return proposal


def _create_checkpoint(cwd: str, kind: str, proposal: dict[str, Any]) -> dict[str, Any]:
    checkpoint_id = f"{kind}_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}_{str(uuid.uuid4())[:6]}"
    files: list[dict[str, Any]] = []
    for mutation in proposal.get("mutations", []):
        rel_path = str(mutation.get("path", ""))
        path = Path(cwd).resolve() / rel_path
        if not path.exists():
            continue
        files.append({"path": rel_path, "content": path.read_text(encoding="utf-8", errors="replace")})
    payload = {
        "checkpoint_id": checkpoint_id,
        "created_utc": _utc_now(),
        "kind": kind,
        "proposal": proposal,
        "files": files,
    }
    checkpoint_path = _checkpoint_root(cwd) / f"{checkpoint_id}.json"
    checkpoint_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    payload["path"] = str(checkpoint_path)
    return payload


def _load_checkpoint(cwd: str, checkpoint_id: str) -> dict[str, Any] | None:
    checkpoint_path = _checkpoint_root(cwd) / f"{checkpoint_id}.json"
    if not checkpoint_path.exists():
        return None
    try:
        payload = json.loads(checkpoint_path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    payload["path"] = str(checkpoint_path)
    return payload


def _restore_files(cwd: str, checkpoint: dict[str, Any]) -> None:
    for file_state in checkpoint.get("files", []):
        rel_path = str(file_state.get("path", ""))
        if not rel_path:
            continue
        path = Path(cwd).resolve() / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(str(file_state.get("content", "")), encoding="utf-8")


def _apply_mutations(cwd: str, proposal: dict[str, Any]) -> list[str]:
    changed_paths: list[str] = []
    spec_map = {spec["key"]: spec for spec in _target_specs(cwd)}
    for mutation in proposal.get("mutations", []):
        spec = spec_map.get(str(mutation.get("key", "")))
        if spec is None:
            continue
        path = Path(spec["path"])
        if not path.exists():
            continue
        content = path.read_text(encoding="utf-8", errors="replace")
        updated, replaced = _replace_value(content, str(spec["pattern"]), int(mutation.get("to", 0) or 0))
        if not replaced:
            continue
        path.write_text(updated, encoding="utf-8")
        changed_paths.append(str(path))
    return changed_paths


def _verification_commands(cwd: str, changed_paths: list[str], mutations: list[dict[str, Any]]) -> list[list[str]]:
    commands: list[list[str]] = []
    if changed_paths:
        commands.append([sys.executable, "-m", "py_compile", *changed_paths])
    unittest_targets = _verification_test_targets(cwd, mutations)
    if unittest_targets:
        commands.append([sys.executable, "-m", "unittest", *unittest_targets, "-q"])
    return commands


def _run_verification(cwd: str, changed_paths: list[str], mutations: list[dict[str, Any]]) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    for command in _verification_commands(cwd, changed_paths, mutations):
        completed = subprocess.run(
            command,
            cwd=str(Path(cwd).resolve()),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        checks.append(
            {
                "command": command,
                "ok": completed.returncode == 0,
                "returncode": completed.returncode,
                "stdout_tail": "\n".join(completed.stdout.splitlines()[-20:]),
                "stderr_tail": "\n".join(completed.stderr.splitlines()[-20:]),
            }
        )
        if completed.returncode != 0:
            break
    return {"ok": all(item["ok"] for item in checks), "checks": checks}


def _render_patch_review_markdown(review: dict[str, Any]) -> str:
    lines = [
        "# Zero AI Guarded Source Evolution Review",
        "",
        f"- Candidate ID: `{review.get('candidate_id', '')}`",
        f"- Ready for canary: `{'yes' if review.get('ready_for_canary', False) else 'no'}`",
        f"- Safe: `{'yes' if review.get('safe', False) else 'no'}`",
        f"- Beneficial: `{'yes' if review.get('beneficial', False) else 'no'}`",
        f"- Mutation count: `{review.get('mutation_count', 0)}`",
        f"- Predicted gain: `{review.get('predicted_gain', 0.0)}`",
        "",
        review.get("summary", ""),
    ]
    blocked = list(review.get("blocked_reasons", []))
    if blocked:
        lines.extend(["", "## Blocked Reasons", ""])
        lines.extend([f"- {item}" for item in blocked])
    changes = list(review.get("changes", []))
    if changes:
        lines.extend(["", "## Proposed Changes", ""])
        for item in changes:
            lines.append(f"### `{item.get('path', '')}`")
            lines.append("")
            lines.append(f"- Label: {item.get('label', '')}")
            lines.append(f"- Value change: `{item.get('from')}` -> `{item.get('to')}`")
            lines.append(f"- Line: `{item.get('line_number')}`")
            lines.append(f"- Before: `{item.get('before_line', '')}`")
            lines.append(f"- After: `{item.get('after_line', '')}`")
            lines.append("")
            lines.append("```diff")
            lines.append(str(item.get("diff", "")).rstrip())
            lines.append("```")
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _build_patch_review(cwd: str, proposal: dict[str, Any]) -> dict[str, Any]:
    spec_map = {spec["key"]: spec for spec in _target_specs(cwd)}
    changes: list[dict[str, Any]] = []
    for mutation in proposal.get("mutations", []):
        spec = spec_map.get(str(mutation.get("key", "")))
        rel_path = str(mutation.get("path", ""))
        path = Path(cwd).resolve() / rel_path
        if spec is None or not path.exists():
            changes.append(
                {
                    "path": rel_path,
                    "label": str(mutation.get("label", "")),
                    "from": mutation.get("from"),
                    "to": mutation.get("to"),
                    "line_number": None,
                    "before_line": "",
                    "after_line": "",
                    "headline": f"{rel_path}: {mutation.get('from')} -> {mutation.get('to')}",
                    "diff": "",
                }
            )
            continue
        before = path.read_text(encoding="utf-8", errors="replace")
        after, replaced = _replace_value(before, str(spec["pattern"]), int(mutation.get("to", 0) or 0))
        line_number = _line_number_for_pattern(before, str(spec["pattern"]))
        diff_text = ""
        after_line = ""
        if replaced:
            diff_text = "".join(
                difflib.unified_diff(
                    before.splitlines(True),
                    after.splitlines(True),
                    fromfile=rel_path,
                    tofile=f"{rel_path} (candidate)",
                    n=2,
                )
            )
            after_line = _line_text(after, line_number)
        changes.append(
            {
                "path": rel_path,
                "label": str(mutation.get("label", "")),
                "from": mutation.get("from"),
                "to": mutation.get("to"),
                "line_number": line_number,
                "before_line": _line_text(before, line_number),
                "after_line": after_line,
                "headline": f"{rel_path}: {mutation.get('label', '')} {mutation.get('from')} -> {mutation.get('to')}",
                "diff": diff_text,
            }
        )

    change_headlines = [str(item.get("headline", "")) for item in changes if str(item.get("headline", ""))]
    summary = "No guarded source changes are proposed right now."
    mutation_count = len(changes)
    if mutation_count > 0:
        file_count = len({str(item.get("path", "")) for item in changes})
        summary = f"{mutation_count} proposed guarded source change(s) across {file_count} file(s)."
    if proposal.get("blocked_reasons"):
        summary = f"{summary} Canary is currently blocked."

    review = {
        "ok": True,
        "candidate_id": str(proposal.get("candidate_id", "")),
        "created_utc": _utc_now(),
        "safe": bool(proposal.get("safe", False)),
        "beneficial": bool(proposal.get("beneficial", False)),
        "ready_for_canary": bool(proposal.get("candidate_available", False))
        and bool(proposal.get("beneficial", False))
        and bool(proposal.get("safe", False)),
        "mutation_count": mutation_count,
        "predicted_gain": float(proposal.get("predicted_gain", 0.0) or 0.0),
        "blocked_reasons": list(proposal.get("blocked_reasons", [])),
        "change_headlines": change_headlines,
        "changes": changes,
        "summary": summary,
    }

    artifact_base = _review_root(cwd) / f"source_evolution_review_{review['candidate_id']}"
    review["artifact_path"] = str(artifact_base.with_suffix(".md"))
    review["artifact_json_path"] = str(artifact_base.with_suffix(".json"))
    artifact_json_payload = dict(review)
    Path(review["artifact_json_path"]).write_text(json.dumps(artifact_json_payload, indent=2) + "\n", encoding="utf-8")
    Path(review["artifact_path"]).write_text(_render_patch_review_markdown(review), encoding="utf-8")
    return review


def _sync_canary_overlay(source_root: Path, target_root: Path) -> None:
    ignore_names = {
        ".git",
        "__pycache__",
        ".pytest_cache",
        "canary_workspaces",
        "bin",
        "obj",
        "dist",
        "publish",
        "installers",
        "msix",
    }
    for name in ("src", "tests", ".zero_os"):
        source = source_root / name
        if not source.exists():
            continue
        target = target_root / name
        if source.is_dir():
            shutil.copytree(
                source,
                target,
                dirs_exist_ok=True,
                ignore=lambda _dir, names: [item for item in names if item in ignore_names],
            )
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)


def _prepare_canary_workspace(cwd: str, candidate_id: str) -> dict[str, Any]:
    source_root = Path(cwd).resolve()
    workspace_root = _canary_workspace_root(cwd)
    sandbox_path = workspace_root / f"candidate_{candidate_id}"
    if sandbox_path.exists():
        shutil.rmtree(sandbox_path, ignore_errors=True)

    repo_root = _git_repo_root(cwd)
    if repo_root is not None:
        completed = subprocess.run(
            ["git", "-C", str(repo_root), "worktree", "add", "--detach", str(sandbox_path), "HEAD"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if completed.returncode == 0 and sandbox_path.exists():
            _sync_canary_overlay(source_root, sandbox_path)
            return {
                "ok": True,
                "mode": "git_worktree",
                "isolated": True,
                "path": str(sandbox_path),
                "repo_root": str(repo_root),
                "overlay": "workspace_sync",
            }

    sandbox_path.mkdir(parents=True, exist_ok=True)
    _sync_canary_overlay(source_root, sandbox_path)
    return {
        "ok": True,
        "mode": "copy_sandbox",
        "isolated": True,
        "path": str(sandbox_path),
        "repo_root": "",
        "overlay": "workspace_sync",
    }


def _cleanup_canary_workspace(cwd: str, workspace: dict[str, Any]) -> dict[str, Any]:
    sandbox_path = Path(str(workspace.get("path", ""))).resolve()
    cleanup = {"ok": True, "removed": False, "mode": str(workspace.get("mode", "")), "path": str(sandbox_path)}
    if not sandbox_path.exists():
        cleanup["removed"] = True
        return cleanup
    if str(workspace.get("mode", "")) == "git_worktree":
        repo_root = str(workspace.get("repo_root", "") or cwd)
        completed = subprocess.run(
            ["git", "-C", repo_root, "worktree", "remove", "--force", str(sandbox_path)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        cleanup["git_returncode"] = completed.returncode
        cleanup["git_stderr_tail"] = "\n".join(completed.stderr.splitlines()[-10:])
    if sandbox_path.exists():
        shutil.rmtree(sandbox_path, ignore_errors=True)
    cleanup["removed"] = not sandbox_path.exists()
    cleanup["ok"] = bool(cleanup["removed"])
    return cleanup


def zero_ai_source_evolution_status(cwd: str) -> dict[str, Any]:
    state = _load_state(cwd)
    proposal = _proposal_from_live(cwd)
    recommended_action = "observe"
    if proposal.get("candidate_available", False) and proposal.get("beneficial", False) and proposal.get("safe", False) and _auto_due(state):
        recommended_action = "auto_run"
    if dict(state.get("pending_candidate") or {}) and bool((state.get("last_canary") or {}).get("passed", False)):
        recommended_action = "promote"

    status = {
        "ok": True,
        "time_utc": _utc_now(),
        "engine_path": str(_state_path(cwd)),
        "history_path": str(_history_path(cwd)),
        "checkpoint_root": str(_checkpoint_root(cwd)),
        "allowed_scopes": state.get("allowed_scopes", []),
        "allowed_scope_count": len(state.get("allowed_scopes", [])),
        "current_source_generation": int(state.get("current_source_generation", 0)),
        "promoted_count": int(state.get("promoted_count", 0)),
        "rollback_count": int(state.get("rollback_count", 0)),
        "auto_enabled": bool(state.get("auto_enabled", True)),
        "min_auto_interval_seconds": int(state.get("min_auto_interval_seconds", 21600)),
        "last_auto_run_utc": str(state.get("last_auto_run_utc", "")),
        "next_auto_run_utc": str(state.get("next_auto_run_utc", "")),
        "due_now": _auto_due(state),
        "source_evolution_ready": bool(proposal.get("safe", False)),
        "sandboxed_patch_lane_ready": bool(proposal.get("sandbox_patch_lane_ready", False)),
        "sandbox_patch_scope_count": int(proposal.get("sandbox_patch_scope_count", 0) or 0),
        "expanded_sandbox_patch_lane": bool(proposal.get("expanded_sandbox_patch_lane", False)),
        "recommended_action": recommended_action,
        "proposal": proposal,
        "pending_candidate": dict(state.get("pending_candidate") or {}),
        "last_proposal": dict(state.get("last_proposal") or {}),
        "last_simulation": dict(state.get("last_simulation") or {}),
        "last_canary": dict(state.get("last_canary") or {}),
        "last_promotion": dict(state.get("last_promotion") or {}),
        "last_rollback": dict(state.get("last_rollback") or {}),
        "recent_history": _history_tail(cwd, limit=8),
    }
    _save_state(cwd, state)
    return status


def zero_ai_source_evolution_propose(cwd: str) -> dict[str, Any]:
    state = _load_state(cwd)
    proposal = _proposal_from_live(cwd)
    state["last_proposal"] = proposal
    _save_state(cwd, state)
    _append_history(
        cwd,
        {
            "time_utc": proposal["time_utc"],
            "action": "propose",
            "candidate_available": proposal.get("candidate_available", False),
            "predicted_gain": proposal.get("predicted_gain", 0.0),
            "summary": proposal.get("summary", ""),
        },
    )
    return {"ok": True, "proposal": proposal, "status": zero_ai_source_evolution_status(cwd)}


def zero_ai_source_evolution_simulate(cwd: str) -> dict[str, Any]:
    state = _load_state(cwd)
    proposal = _proposal_from_live(cwd)
    simulation = {
        "ok": True,
        "time_utc": _utc_now(),
        "candidate_id": proposal.get("candidate_id", ""),
        "candidate_available": proposal.get("candidate_available", False),
        "safe": proposal.get("safe", False),
        "beneficial": proposal.get("beneficial", False),
        "blocked_reasons": proposal.get("blocked_reasons", []),
        "mutations": proposal.get("mutations", []),
        "predicted_gain": proposal.get("predicted_gain", 0.0),
        "verification_plan": proposal.get("verification_plan", {}),
        "ready_for_canary": bool(proposal.get("candidate_available", False))
        and bool(proposal.get("beneficial", False))
        and bool(proposal.get("safe", False)),
        "summary": proposal.get("summary", ""),
    }
    state["last_proposal"] = proposal
    state["last_simulation"] = simulation
    _save_state(cwd, state)
    _append_history(
        cwd,
        {
            "time_utc": simulation["time_utc"],
            "action": "simulate",
            "safe": simulation["safe"],
            "beneficial": simulation["beneficial"],
            "predicted_gain": simulation["predicted_gain"],
        },
    )
    return simulation


def zero_ai_source_evolution_canary(cwd: str) -> dict[str, Any]:
    state = _load_state(cwd)
    simulation = zero_ai_source_evolution_simulate(cwd)
    if not bool(simulation.get("ready_for_canary", False)):
        report = {
            "ok": False,
            "blocked": True,
            "reason": "guarded source evolution candidate is not ready for canary",
            "simulation": simulation,
        }
        state["last_canary"] = report
        _save_state(cwd, state)
        return report

    checkpoint = _create_checkpoint(cwd, "canary", simulation)
    workspace = _prepare_canary_workspace(cwd, str(simulation.get("candidate_id", "") or str(uuid.uuid4())[:10]))
    changed_paths: list[str] = []
    verification = {"ok": False, "checks": []}
    cleanup = {"ok": False, "removed": False, "mode": str(workspace.get("mode", "")), "path": str(workspace.get("path", ""))}
    try:
        sandbox_cwd = str(workspace.get("path", cwd))
        changed_paths = _apply_mutations(sandbox_cwd, simulation)
        verification = _run_verification(sandbox_cwd, changed_paths, list(simulation.get("mutations", [])))
    finally:
        cleanup = _cleanup_canary_workspace(cwd, workspace)

    passed = bool(verification.get("ok", False))
    canary = {
        "ok": passed,
        "time_utc": _utc_now(),
        "passed": passed,
        "checkpoint": checkpoint,
        "workspace": workspace,
        "cleanup": cleanup,
        "candidate_id": simulation.get("candidate_id", ""),
        "changed_paths": changed_paths,
        "verification": verification,
        "summary": "guarded source evolution candidate passed canary verification"
        if passed
        else "guarded source evolution candidate failed canary verification",
    }
    if passed:
        state["pending_candidate"] = {
            "candidate_id": str(simulation.get("candidate_id", "")),
            "checkpoint_id": checkpoint["checkpoint_id"],
            "mutations": list(simulation.get("mutations", [])),
        }
    else:
        state["pending_candidate"] = {}
    state["last_canary"] = canary
    _save_state(cwd, state)
    _append_history(
        cwd,
        {
            "time_utc": canary["time_utc"],
            "action": "canary",
            "passed": passed,
            "candidate_id": canary["candidate_id"],
        },
    )
    return canary


def zero_ai_source_evolution_promote(cwd: str) -> dict[str, Any]:
    state = _load_state(cwd)
    pending = dict(state.get("pending_candidate") or {})
    last_canary = dict(state.get("last_canary") or {})
    if not pending or not bool(last_canary.get("passed", False)):
        return {
            "ok": False,
            "blocked": True,
            "reason": "no successful guarded source evolution canary is waiting for promotion",
            "status": zero_ai_source_evolution_status(cwd),
        }

    promotion_checkpoint = _create_checkpoint(cwd, "promotion", {"mutations": pending.get("mutations", [])})
    applied_paths = _apply_mutations(cwd, {"mutations": pending.get("mutations", [])})
    verification = _run_verification(cwd, applied_paths, list(pending.get("mutations", [])))
    if not bool(verification.get("ok", False)):
        _restore_files(cwd, promotion_checkpoint)
        state["last_canary"] = {
            **last_canary,
            "passed": False,
            "verification": verification,
            "summary": "guarded source evolution promotion verification failed and was rolled back",
        }
        state["pending_candidate"] = {}
        _save_state(cwd, state)
        return {
            "ok": False,
            "blocked": True,
            "reason": "promotion verification failed",
            "verification": verification,
            "status": zero_ai_source_evolution_status(cwd),
        }

    state["current_source_generation"] = int(state.get("current_source_generation", 0)) + 1
    state["promoted_count"] = int(state.get("promoted_count", 0)) + 1
    state["pending_candidate"] = {}
    promotion = {
        "ok": True,
        "time_utc": _utc_now(),
        "generation": state["current_source_generation"],
        "checkpoint": promotion_checkpoint,
        "changed_paths": applied_paths,
        "verification": verification,
        "summary": "guarded source evolution candidate promoted",
    }
    state["last_promotion"] = promotion
    _schedule_next_auto_run(state)
    _save_state(cwd, state)
    _append_history(
        cwd,
        {
            "time_utc": promotion["time_utc"],
            "action": "promote",
            "generation": promotion["generation"],
            "changed_paths": applied_paths,
        },
    )
    return {"ok": True, "promotion": promotion, "status": zero_ai_source_evolution_status(cwd)}


def zero_ai_source_evolution_rollback(cwd: str) -> dict[str, Any]:
    state = _load_state(cwd)
    checkpoint_id = str((state.get("last_promotion") or {}).get("checkpoint", {}).get("checkpoint_id", ""))
    if not checkpoint_id:
        checkpoint_id = str((state.get("last_canary") or {}).get("checkpoint", {}).get("checkpoint_id", ""))
    if not checkpoint_id:
        return {
            "ok": False,
            "blocked": True,
            "reason": "no guarded source evolution checkpoint is available for rollback",
            "status": zero_ai_source_evolution_status(cwd),
        }

    checkpoint = _load_checkpoint(cwd, checkpoint_id)
    if checkpoint is None:
        return {
            "ok": False,
            "blocked": True,
            "reason": f"guarded source evolution checkpoint not found: {checkpoint_id}",
            "status": zero_ai_source_evolution_status(cwd),
        }

    _restore_files(cwd, checkpoint)
    state["rollback_count"] = int(state.get("rollback_count", 0)) + 1
    state["pending_candidate"] = {}
    rollback = {
        "ok": True,
        "time_utc": _utc_now(),
        "checkpoint": checkpoint,
        "summary": "guarded source evolution rollback restored the last checkpoint",
    }
    state["last_rollback"] = rollback
    _save_state(cwd, state)
    _append_history(
        cwd,
        {
            "time_utc": rollback["time_utc"],
            "action": "rollback",
            "checkpoint_id": checkpoint_id,
        },
    )
    return {"ok": True, "rollback": rollback, "status": zero_ai_source_evolution_status(cwd)}


def zero_ai_source_evolution_auto_run(cwd: str) -> dict[str, Any]:
    state = _load_state(cwd)
    status_before = zero_ai_source_evolution_status(cwd)
    if not bool(status_before.get("auto_enabled", True)):
        return {"ok": False, "blocked": True, "reason": "guarded source evolution is disabled", "status": status_before}
    if not bool(status_before.get("due_now", False)):
        return {"ok": True, "changed": False, "reason": "guarded source evolution is not due yet", "status": status_before}

    simulation = zero_ai_source_evolution_simulate(cwd)
    if not bool(simulation.get("candidate_available", False)):
        _schedule_next_auto_run(state)
        _save_state(cwd, state)
        return {
            "ok": True,
            "changed": False,
            "reason": "no guarded source evolution candidate is available right now",
            "simulation": simulation,
            "status": zero_ai_source_evolution_status(cwd),
        }
    if not bool(simulation.get("ready_for_canary", False)):
        _schedule_next_auto_run(state)
        _save_state(cwd, state)
        return {
            "ok": False,
            "changed": False,
            "reason": "guarded source evolution candidate did not pass simulation",
            "simulation": simulation,
            "status": zero_ai_source_evolution_status(cwd),
        }

    canary = zero_ai_source_evolution_canary(cwd)
    if not bool(canary.get("ok", False)):
        _schedule_next_auto_run(state)
        _save_state(cwd, state)
        return {
            "ok": False,
            "changed": False,
            "reason": "guarded source evolution canary failed",
            "simulation": simulation,
            "canary": canary,
            "status": zero_ai_source_evolution_status(cwd),
        }

    promotion = zero_ai_source_evolution_promote(cwd)
    return {
        "ok": bool(promotion.get("ok", False)),
        "changed": bool(promotion.get("ok", False)),
        "simulation": simulation,
        "canary": canary,
        "promotion": promotion.get("promotion", {}),
        "status": zero_ai_source_evolution_status(cwd),
    }


def zero_ai_source_evolution_generate_upgrade(cwd: str) -> dict[str, Any]:
    result = zero_ai_source_evolution_propose(cwd)
    proposal = dict(result.get("proposal") or {})
    next_action = "canary" if bool(proposal.get("candidate_available", False)) and bool(proposal.get("safe", False)) and bool(proposal.get("beneficial", False)) else "stabilize"
    return {
        "ok": True,
        "auto_generated": True,
        "generated_by": "zero_ai",
        "upgrade_kind": "guarded_source_patch",
        "generation_mode": "auto_candidate",
        "next_action": next_action,
        "proposal": proposal,
        "status": result.get("status", {}),
    }


def zero_ai_source_evolution_auto_upgrade(cwd: str) -> dict[str, Any]:
    result = zero_ai_source_evolution_auto_run(cwd)
    enriched = dict(result)
    enriched["auto_generated"] = True
    enriched["generated_by"] = "zero_ai"
    enriched["upgrade_kind"] = "guarded_source_patch"
    enriched["generation_mode"] = "auto_candidate"
    return enriched
