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

from zero_os.architecture_promotion_authority import evaluate_architecture_promotion
from zero_os.authority_runtime_integration_audit import audit_authority_runtime_integration
from zero_os.execution_authority_ticket import acknowledge_consumed_execution_ticket
from zero_os.independent_outcome_verifier import OutcomeEvidence, verify_outcome
from zero_os.protected_correction_plane import CorrectionCandidate, default_correction_plane
from zero_os.whole_repo_capability_audit import audit_python_file


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
    data = dict(payload)
    data["updated_utc"] = _utc_now()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


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
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


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
        "schema_version": 2,
        "authority_model": "v5_protected_correction_plane",
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
    merged_scopes = [str(item) for item in state.get("allowed_scopes", [])]
    for scope in default["allowed_scopes"]:
        if scope not in merged_scopes:
            merged_scopes.append(scope)
    state["allowed_scopes"] = merged_scopes
    state["schema_version"] = 2
    state["authority_model"] = "v5_protected_correction_plane"
    return state


def _save_state(cwd: str, state: dict[str, Any]) -> dict[str, Any]:
    _save_json(_state_path(cwd), state)
    return state


def _target_specs(cwd: str) -> list[dict[str, Any]]:
    root = Path(cwd).resolve()
    out: list[dict[str, Any]] = []
    for definition in _target_spec_definitions():
        spec = dict(definition)
        spec["path"] = str(root / str(spec["relative_path"]))
        out.append(spec)
    return out


def _candidate_id(target_profile: dict[str, Any], mutations: list[dict[str, Any]]) -> str:
    payload = {
        "profile": target_profile,
        "mutations": [{"key": item.get("key"), "path": item.get("path"), "from": item.get("from"), "to": item.get("to")} for item in mutations],
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()[:10]


def _extract_current_value(content: str, pattern: str) -> int | None:
    match = re.search(pattern, content, flags=re.S)
    if not match:
        return None
    try:
        return int(match.group(2))
    except (IndexError, TypeError, ValueError):
        return None


def _replace_value(content: str, pattern: str, new_value: int) -> tuple[str, bool]:
    updated, count = re.subn(pattern, lambda match: f"{match.group(1)}{int(new_value)}", content, count=1, flags=re.S)
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
    index = int(line_number) - 1
    return lines[index].strip() if 0 <= index < len(lines) else ""


def _auto_due(state: dict[str, Any]) -> bool:
    if not bool(state.get("auto_enabled", True)):
        return False
    next_run = _parse_utc(str(state.get("next_auto_run_utc", "")))
    return next_run is None or datetime.now(timezone.utc) >= next_run


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
    if dict(evolution_status.get("pending_candidate") or {}):
        reasons.append("bounded evolution still has a pending candidate")
    if str(evolution_status.get("recommended_action", "observe")) not in {"observe", "promote"}:
        reasons.append("bounded evolution should settle before source evolution")
    return (not reasons, reasons)


def _derive_self_repair_floor(cwd: str) -> int:
    status = _load_json(Path(cwd).resolve() / ".zero_os" / "runtime" / "phase_runtime_status.json", {"runtime_score": 0.0})
    score = float(status.get("runtime_score", 0.0) or 0.0)
    return 0 if score <= 0 else max(60, min(90, int(score) - 10))


def _clamp_interval(value: int, minimum: int = 60, maximum: int = 3600) -> int:
    return max(minimum, min(maximum, int(value)))


def _derive_continuity_interval(cwd: str) -> int:
    from zero_os.self_continuity import zero_ai_continuity_governance_auto_status

    status = zero_ai_continuity_governance_auto_status(cwd)
    if not bool(status.get("current_enabled", False)) and not bool(status.get("recommended_enabled", False)):
        return 0
    value = int(status.get("current_interval_seconds", 0) or status.get("recommended_interval_seconds", 0) or 0)
    return _clamp_interval(value) if value > 0 else 0


def _derive_triad_interval(cwd: str) -> int:
    from zero_os.triad_balance import triad_ops_status

    status = triad_ops_status(cwd)
    return _clamp_interval(int(status.get("interval_seconds", 0) or 0)) if bool(status.get("enabled", False)) else 0


def _derive_antivirus_interval(cwd: str) -> int:
    from zero_os.antivirus import monitor_status

    status = monitor_status(cwd)
    return _clamp_interval(int(status.get("interval_seconds", 0) or 0)) if bool(status.get("enabled", False)) else 0


def _target_profile_from_live(cwd: str, evolution_status: dict[str, Any]) -> dict[str, int]:
    profile = dict(evolution_status.get("current_profile") or {})
    return {
        "runtime_loop_interval_seconds": int(profile.get("runtime_loop_interval_seconds", 0) or 0),
        "autonomy_loop_interval_seconds": int(profile.get("autonomy_loop_interval_seconds", 0) or 0),
        "self_repair_minimum_readiness_floor": _derive_self_repair_floor(cwd),
        "continuity_governance_interval_seconds": _derive_continuity_interval(cwd),
        "triad_ops_interval_seconds": _derive_triad_interval(cwd),
        "antivirus_monitor_interval_seconds": _derive_antivirus_interval(cwd),
    }


def _verification_test_targets(cwd: str, mutations: list[dict[str, Any]]) -> list[str]:
    root = Path(cwd).resolve()
    modules = ["tests.test_zero_ai_evolution", "tests.test_zero_ai_source_evolution"]
    for mutation in mutations:
        hint = str(mutation.get("test_hint", "")).strip()
        if hint and hint not in modules:
            modules.append(hint)
    out: list[str] = []
    for module in modules:
        if (root / Path(*module.split(".")).with_suffix(".py")).exists():
            out.append(module)
    return out


def _proposal_from_live(cwd: str) -> dict[str, Any]:
    from zero_os.zero_ai_evolution import zero_ai_evolution_status

    evolution = zero_ai_evolution_status(cwd)
    ready, ready_reasons = _source_ready(evolution)
    target_profile = _target_profile_from_live(cwd, evolution)
    mutations: list[dict[str, Any]] = []
    missing_files: list[str] = []
    specs = _target_specs(cwd)
    spec_map = {str(item.get("key", "")): item for item in specs}

    for spec in specs:
        path = Path(str(spec["path"]))
        if not path.exists():
            missing_files.append(str(spec["relative_path"]))
            continue
        content = path.read_text(encoding="utf-8", errors="replace")
        current = _extract_current_value(content, str(spec["pattern"]))
        target = int(target_profile.get(str(spec["target_key"]), 0) or 0)
        if current is None:
            missing_files.append(str(spec["relative_path"]))
            continue
        if target > 0 and current != target:
            mutations.append(
                {
                    "key": spec["key"],
                    "label": spec["label"],
                    "path": spec["relative_path"],
                    "from": current,
                    "to": target,
                    "test_hint": spec["test_hint"],
                    "scope": spec["scope"],
                    "lane_kind": spec["lane_kind"],
                }
            )

    sandbox_specs = [item for item in specs if str(item.get("lane_kind", "")) == "sandbox_patch"]
    missing_sandbox = [item["relative_path"] for item in sandbox_specs if item["relative_path"] in missing_files]
    sandbox_targets = [item for item in mutations if str(spec_map.get(str(item.get("key", "")), {}).get("lane_kind", "")) == "sandbox_patch"]
    safe = ready and not missing_files
    candidate = {
        "ok": True,
        "candidate_id": _candidate_id(target_profile, mutations),
        "time_utc": _utc_now(),
        "generated_by": "zero_ai",
        "upgrade_kind": "guarded_source_patch",
        "generation_mode": "auto_candidate",
        "candidate_available": bool(mutations),
        "beneficial": bool(mutations),
        "safe": safe,
        "blocked_reasons": ([] if ready else ready_reasons) + [f"missing allowlisted source file: {path}" for path in missing_files],
        "current_profile": target_profile,
        "mutations": mutations,
        "sandbox_patch_lane_ready": safe and bool(sandbox_specs) and not missing_sandbox,
        "sandbox_patch_targets": sandbox_targets,
        "sandbox_patch_scope_count": len(sandbox_specs),
        "expanded_sandbox_patch_lane": safe and len(sandbox_specs) >= 3 and not missing_sandbox,
        "predicted_gain": round(len(mutations) * 3.5, 2) if mutations else 0.0,
        "verification_plan": {
            "py_compile": [str(item.get("path", "")) for item in mutations],
            "tests": _verification_test_targets(cwd, mutations),
        },
    }
    candidate["summary"] = (
        "guarded source candidate requires constitutional promotion authority"
        if mutations and safe
        else "source defaults already match or source evolution is not ready"
    )
    review = _build_patch_review(cwd, candidate)
    candidate["patch_review"] = review
    candidate["patch_review_path"] = str(review.get("artifact_path", ""))
    candidate["patch_review_json_path"] = str(review.get("artifact_json_path", ""))
    candidate["patch_review_summary"] = str(review.get("summary", ""))
    candidate["patch_review_headlines"] = list(review.get("change_headlines", []))
    return candidate


def _create_checkpoint(cwd: str, kind: str, proposal: dict[str, Any]) -> dict[str, Any]:
    checkpoint_id = f"{kind}_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}_{str(uuid.uuid4())[:6]}"
    files: list[dict[str, Any]] = []
    for mutation in proposal.get("mutations", []):
        rel = str(mutation.get("path", ""))
        path = Path(cwd).resolve() / rel
        if path.exists():
            files.append({"path": rel, "content": path.read_text(encoding="utf-8", errors="replace")})
    payload = {"checkpoint_id": checkpoint_id, "created_utc": _utc_now(), "kind": kind, "proposal": proposal, "files": files}
    path = _checkpoint_root(cwd) / f"{checkpoint_id}.json"
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    payload["path"] = str(path)
    return payload


def _load_checkpoint(cwd: str, checkpoint_id: str) -> dict[str, Any] | None:
    path = _checkpoint_root(cwd) / f"{checkpoint_id}.json"
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _restore_files(cwd: str, checkpoint: dict[str, Any]) -> None:
    for item in checkpoint.get("files", []):
        rel = str(item.get("path", ""))
        if not rel:
            continue
        path = Path(cwd).resolve() / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(str(item.get("content", "")), encoding="utf-8")


def _apply_mutations(cwd: str, proposal: dict[str, Any]) -> list[str]:
    changed: list[str] = []
    specs = {str(item["key"]): item for item in _target_specs(cwd)}
    for mutation in proposal.get("mutations", []):
        spec = specs.get(str(mutation.get("key", "")))
        if spec is None:
            continue
        path = Path(str(spec["path"]))
        if not path.exists():
            continue
        before = path.read_text(encoding="utf-8", errors="replace")
        after, replaced = _replace_value(before, str(spec["pattern"]), int(mutation.get("to", 0) or 0))
        if replaced:
            path.write_text(after, encoding="utf-8")
            changed.append(str(path))
    return changed


def _verification_commands(cwd: str, changed_paths: list[str], mutations: list[dict[str, Any]]) -> list[list[str]]:
    commands: list[list[str]] = []
    if changed_paths:
        commands.append([sys.executable, "-m", "py_compile", *changed_paths])
    tests = _verification_test_targets(cwd, mutations)
    if tests:
        commands.append([sys.executable, "-m", "unittest", *tests, "-q"])
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
    return {"ok": bool(checks) and all(bool(item["ok"]) for item in checks), "checks": checks}


def _render_patch_review_markdown(review: dict[str, Any]) -> str:
    lines = [
        "# Zero AI Guarded Source Evolution Review",
        "",
        f"- Candidate ID: `{review.get('candidate_id', '')}`",
        f"- Ready for canary: `{'yes' if review.get('ready_for_canary', False) else 'no'}`",
        f"- Mutation count: `{review.get('mutation_count', 0)}`",
        "",
        str(review.get("summary", "")),
    ]
    for item in review.get("changes", []):
        lines.extend(
            [
                "",
                f"### `{item.get('path', '')}`",
                f"- Value change: `{item.get('from')}` -> `{item.get('to')}`",
                f"- Line: `{item.get('line_number')}`",
                "```diff",
                str(item.get("diff", "")).rstrip(),
                "```",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def _build_patch_review(cwd: str, proposal: dict[str, Any]) -> dict[str, Any]:
    specs = {str(item["key"]): item for item in _target_specs(cwd)}
    changes: list[dict[str, Any]] = []
    for mutation in proposal.get("mutations", []):
        spec = specs.get(str(mutation.get("key", "")))
        rel = str(mutation.get("path", ""))
        path = Path(cwd).resolve() / rel
        before = path.read_text(encoding="utf-8", errors="replace") if spec is not None and path.exists() else ""
        after, replaced = _replace_value(before, str(spec["pattern"]), int(mutation.get("to", 0) or 0)) if spec is not None and before else ("", False)
        line_number = _line_number_for_pattern(before, str(spec["pattern"])) if spec is not None and before else None
        diff_text = ""
        if replaced:
            diff_text = "".join(difflib.unified_diff(before.splitlines(True), after.splitlines(True), fromfile=rel, tofile=f"{rel} (candidate)", n=2))
        changes.append(
            {
                "path": rel,
                "label": str(mutation.get("label", "")),
                "from": mutation.get("from"),
                "to": mutation.get("to"),
                "line_number": line_number,
                "before_line": _line_text(before, line_number),
                "after_line": _line_text(after, line_number) if replaced else "",
                "headline": f"{rel}: {mutation.get('from')} -> {mutation.get('to')}",
                "diff": diff_text,
            }
        )

    review = {
        "ok": True,
        "candidate_id": str(proposal.get("candidate_id", "")),
        "created_utc": _utc_now(),
        "safe": bool(proposal.get("safe", False)),
        "beneficial": bool(proposal.get("beneficial", False)),
        "ready_for_canary": bool(proposal.get("candidate_available", False)) and bool(proposal.get("safe", False)),
        "mutation_count": len(changes),
        "predicted_gain": float(proposal.get("predicted_gain", 0.0) or 0.0),
        "blocked_reasons": list(proposal.get("blocked_reasons", [])),
        "change_headlines": [str(item["headline"]) for item in changes],
        "changes": changes,
        "summary": f"{len(changes)} guarded source change(s); live promotion requires v5 constitutional authority.",
    }
    base = _review_root(cwd) / f"source_evolution_review_{review['candidate_id']}"
    review["artifact_path"] = str(base.with_suffix(".md"))
    review["artifact_json_path"] = str(base.with_suffix(".json"))
    Path(review["artifact_json_path"]).write_text(json.dumps(review, indent=2) + "\n", encoding="utf-8")
    Path(review["artifact_path"]).write_text(_render_patch_review_markdown(review), encoding="utf-8")
    return review


def _git_repo_root(cwd: str) -> Path | None:
    completed = subprocess.run(["git", "-C", str(Path(cwd).resolve()), "rev-parse", "--show-toplevel"], capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
    if completed.returncode != 0 or not completed.stdout.strip():
        return None
    path = Path(completed.stdout.strip()).resolve()
    return path if path.exists() else None


def _sync_canary_overlay(source_root: Path, target_root: Path) -> None:
    ignore_names = {".git", "__pycache__", ".pytest_cache", "canary_workspaces", "bin", "obj", "dist", "publish", "installers", "msix"}
    for name in ("src", "tests", ".zero_os"):
        source = source_root / name
        if not source.exists():
            continue
        target = target_root / name
        if source.is_dir():
            shutil.copytree(source, target, dirs_exist_ok=True, ignore=lambda _dir, names: [item for item in names if item in ignore_names])
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)


def _prepare_canary_workspace(cwd: str, candidate_id: str) -> dict[str, Any]:
    source_root = Path(cwd).resolve()
    sandbox = _canary_workspace_root(cwd) / f"candidate_{candidate_id}"
    if sandbox.exists():
        shutil.rmtree(sandbox, ignore_errors=True)
    repo = _git_repo_root(cwd)
    if repo is not None:
        completed = subprocess.run(["git", "-C", str(repo), "worktree", "add", "--detach", str(sandbox), "HEAD"], capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
        if completed.returncode == 0 and sandbox.exists():
            _sync_canary_overlay(source_root, sandbox)
            return {"ok": True, "mode": "git_worktree", "isolated": True, "path": str(sandbox), "repo_root": str(repo)}
    sandbox.mkdir(parents=True, exist_ok=True)
    _sync_canary_overlay(source_root, sandbox)
    return {"ok": True, "mode": "copy_sandbox", "isolated": True, "path": str(sandbox), "repo_root": ""}


def _cleanup_canary_workspace(cwd: str, workspace: dict[str, Any]) -> dict[str, Any]:
    sandbox = Path(str(workspace.get("path", ""))).resolve()
    if str(workspace.get("mode", "")) == "git_worktree" and sandbox.exists():
        subprocess.run(["git", "-C", str(workspace.get("repo_root", cwd)), "worktree", "remove", "--force", str(sandbox)], capture_output=True, text=True, check=False)
    if sandbox.exists():
        shutil.rmtree(sandbox, ignore_errors=True)
    return {"ok": not sandbox.exists(), "removed": not sandbox.exists(), "mode": str(workspace.get("mode", "")), "path": str(sandbox)}


def _scoped_capability_bypass_count(cwd: str, mutations: list[dict[str, Any]]) -> int:
    root = Path(cwd).resolve()
    count = 0
    for mutation in mutations:
        path = root / str(mutation.get("path", ""))
        if not path.exists() or path.suffix != ".py":
            continue
        count += sum(1 for sink in audit_python_file(path, root) if not sink.mediated)
    return count


def _readback_matches(cwd: str, mutations: list[dict[str, Any]]) -> bool:
    specs = {str(item["key"]): item for item in _target_specs(cwd)}
    for mutation in mutations:
        spec = specs.get(str(mutation.get("key", "")))
        if spec is None:
            return False
        path = Path(str(spec["path"]))
        if not path.exists():
            return False
        value = _extract_current_value(path.read_text(encoding="utf-8", errors="replace"), str(spec["pattern"]))
        if value != int(mutation.get("to", 0) or 0):
            return False
    return True


def zero_ai_source_evolution_status(cwd: str) -> dict[str, Any]:
    state = _load_state(cwd)
    proposal = _proposal_from_live(cwd)
    pending = dict(state.get("pending_candidate") or {})
    canary_passed = bool((state.get("last_canary") or {}).get("passed", False))
    recommended = "observe"
    if pending and canary_passed:
        recommended = "request_promotion_authority"
    elif proposal.get("candidate_available") and proposal.get("safe") and _auto_due(state):
        recommended = "canary"
    status = {
        "ok": True,
        "time_utc": _utc_now(),
        "engine_path": str(_state_path(cwd)),
        "history_path": str(_history_path(cwd)),
        "checkpoint_root": str(_checkpoint_root(cwd)),
        "authority_model": "v5_protected_correction_plane",
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
        "recommended_action": recommended,
        "proposal": proposal,
        "pending_candidate": pending,
        "last_proposal": dict(state.get("last_proposal") or {}),
        "last_simulation": dict(state.get("last_simulation") or {}),
        "last_canary": dict(state.get("last_canary") or {}),
        "last_promotion": dict(state.get("last_promotion") or {}),
        "last_rollback": dict(state.get("last_rollback") or {}),
        "recent_history": _history_tail(cwd, 8),
    }
    _save_state(cwd, state)
    return status


def zero_ai_source_evolution_propose(cwd: str) -> dict[str, Any]:
    state = _load_state(cwd)
    proposal = _proposal_from_live(cwd)
    state["last_proposal"] = proposal
    _save_state(cwd, state)
    _append_history(cwd, {"time_utc": proposal["time_utc"], "action": "propose", "candidate_available": proposal.get("candidate_available", False), "summary": proposal.get("summary", "")})
    return {"ok": True, "proposal": proposal, "status": zero_ai_source_evolution_status(cwd)}


def zero_ai_source_evolution_simulate(cwd: str) -> dict[str, Any]:
    state = _load_state(cwd)
    proposal = _proposal_from_live(cwd)
    simulation = {
        **proposal,
        "ready_for_canary": bool(proposal.get("candidate_available", False)) and bool(proposal.get("safe", False)) and bool(proposal.get("beneficial", False)),
        "simulated": True,
    }
    state["last_simulation"] = simulation
    _save_state(cwd, state)
    _append_history(cwd, {"time_utc": _utc_now(), "action": "simulate", "safe": simulation.get("safe", False), "beneficial": simulation.get("beneficial", False)})
    return simulation


def zero_ai_source_evolution_canary(cwd: str) -> dict[str, Any]:
    state = _load_state(cwd)
    simulation = zero_ai_source_evolution_simulate(cwd)
    if not bool(simulation.get("ready_for_canary", False)):
        report = {"ok": False, "blocked": True, "reason": "guarded source evolution candidate is not ready for canary", "simulation": simulation}
        state["last_canary"] = report
        _save_state(cwd, state)
        return report

    checkpoint = _create_checkpoint(cwd, "canary", simulation)
    workspace = _prepare_canary_workspace(cwd, str(simulation.get("candidate_id", "")))
    changed: list[str] = []
    verification = {"ok": False, "checks": []}
    cleanup: dict[str, Any] = {}
    try:
        sandbox_cwd = str(workspace.get("path", cwd))
        changed = _apply_mutations(sandbox_cwd, simulation)
        verification = _run_verification(sandbox_cwd, changed, list(simulation.get("mutations", [])))
    finally:
        cleanup = _cleanup_canary_workspace(cwd, workspace)

    passed = bool(verification.get("ok", False)) and bool(cleanup.get("ok", False))
    canary = {
        "ok": passed,
        "time_utc": _utc_now(),
        "passed": passed,
        "candidate_id": simulation.get("candidate_id", ""),
        "checkpoint": checkpoint,
        "workspace": workspace,
        "cleanup": cleanup,
        "changed_paths": changed,
        "verification": verification,
        "summary": "isolated canary passed; live promotion still requires v5 authority" if passed else "isolated canary failed",
    }
    state["last_canary"] = canary
    state["pending_candidate"] = {
        "candidate_id": str(simulation.get("candidate_id", "")),
        "checkpoint_id": str(checkpoint.get("checkpoint_id", "")),
        "mutations": list(simulation.get("mutations", [])),
    } if passed else {}
    _save_state(cwd, state)
    _append_history(cwd, {"time_utc": canary["time_utc"], "action": "canary", "passed": passed, "candidate_id": canary["candidate_id"]})
    return canary


def zero_ai_source_evolution_promote(cwd: str) -> dict[str, Any]:
    state = _load_state(cwd)
    pending = dict(state.get("pending_candidate") or {})
    last_canary = dict(state.get("last_canary") or {})
    if not pending or not bool(last_canary.get("passed", False)):
        return {"ok": False, "blocked": True, "reason": "no successful guarded source canary is waiting for promotion", "status": zero_ai_source_evolution_status(cwd)}

    handoff = acknowledge_consumed_execution_ticket(cwd, "self_upgrade", max_handoff_seconds=10)
    if not bool(handoff.get("ok", False)):
        return {
            "ok": False,
            "blocked": True,
            "reason": "constitutional_self_upgrade_handoff_missing",
            "authority": handoff,
            "status": zero_ai_source_evolution_status(cwd),
        }

    verification = dict(last_canary.get("verification") or {})
    check_labels = tuple(
        " ".join(str(x) for x in item.get("command", []))
        for item in list(verification.get("checks", []))
        if bool(item.get("ok", False))
    ) or ("isolated_canary_verification_passed",)
    canary_outcome = verify_outcome(
        actor_id="zero_ai_source_evolution",
        expected_state="isolated_candidate_survived",
        evidence=[
            OutcomeEvidence("canary-verifier", "isolated_execution", "passed" if last_canary.get("passed") else "failed", bool(last_canary.get("passed")), ("canary_workspace",)),
            OutcomeEvidence("cleanup-verifier", "sandbox_cleanup", "clean" if (last_canary.get("cleanup") or {}).get("ok") else "dirty", bool((last_canary.get("cleanup") or {}).get("ok")), ("filesystem_cleanup",)),
        ],
        required_independent_groups=2,
    )
    candidate = CorrectionCandidate(
        candidate_id=str(pending.get("candidate_id", "")),
        target="zero_os_source",
        proposer_id="zero_ai_source_evolution",
        provenance=("guarded_source_proposal", str(pending.get("candidate_id", ""))),
        invariant_checks=check_labels,
        pressure_results=("isolated_canary_passed",),
        independent_evaluators=("canary-verifier", "runtime-integration-auditor"),
        rollback_reference=str(pending.get("checkpoint_id", "")),
        canary_reference=str(last_canary.get("candidate_id", "")),
        compatibility_reference="targeted_compile_and_test_plan",
    )
    integration = audit_authority_runtime_integration(cwd)
    scoped_bypasses = _scoped_capability_bypass_count(cwd, list(pending.get("mutations", [])))
    promotion_authority = evaluate_architecture_promotion(
        candidate=candidate,
        correction_plane=default_correction_plane(),
        critical_invariants_passed=bool(verification.get("ok", False)),
        independent_outcome_verified=canary_outcome.verified,
        identified_authority_bypasses=int(integration.get("critical_failure_count", 0) or 0),
        identified_capability_bypasses=scoped_bypasses,
        demonstrated_scope=[str(item.get("scope", "")) for item in pending.get("mutations", []) if str(item.get("scope", ""))],
        unresolved_scope=["dynamic_runtime_behavior", "dependency_behavior", "native_and_hardware_scope"],
        runtime_integration_report=integration,
    )
    if not promotion_authority.promote:
        return {
            "ok": False,
            "blocked": True,
            "reason": "architecture_promotion_authority_denied",
            "authority": handoff,
            "promotion_authority": promotion_authority,
            "runtime_integration": integration,
            "scoped_capability_bypasses": scoped_bypasses,
            "status": zero_ai_source_evolution_status(cwd),
        }

    checkpoint = _create_checkpoint(cwd, "promotion", {"mutations": pending.get("mutations", [])})
    applied = _apply_mutations(cwd, {"mutations": pending.get("mutations", [])})
    post_verification = _run_verification(cwd, applied, list(pending.get("mutations", [])))
    readback_ok = _readback_matches(cwd, list(pending.get("mutations", [])))
    outcome = verify_outcome(
        actor_id="zero_ai_source_evolution",
        expected_state="promoted_source_matches_candidate",
        evidence=[
            OutcomeEvidence("source-readback-verifier", "source_readback", "match" if readback_ok else "mismatch", readback_ok, ("source_files",)),
            OutcomeEvidence("post-promotion-test-verifier", "post_promotion_verification", "pass" if post_verification.get("ok") else "fail", bool(post_verification.get("ok")), ("test_process",)),
        ],
        required_independent_groups=2,
    )
    if not outcome.verified:
        _restore_files(cwd, checkpoint)
        state["pending_candidate"] = {}
        state["last_canary"] = {**last_canary, "passed": False, "summary": "promotion contradicted post-write outcome and was rolled back"}
        _save_state(cwd, state)
        return {
            "ok": False,
            "blocked": True,
            "reason": "independent_post_promotion_outcome_failed",
            "rolled_back": True,
            "outcome": outcome,
            "verification": post_verification,
            "status": zero_ai_source_evolution_status(cwd),
        }

    state["current_source_generation"] = int(state.get("current_source_generation", 0)) + 1
    state["promoted_count"] = int(state.get("promoted_count", 0)) + 1
    state["pending_candidate"] = {}
    promotion = {
        "ok": True,
        "time_utc": _utc_now(),
        "generation": state["current_source_generation"],
        "checkpoint": checkpoint,
        "changed_paths": applied,
        "verification": post_verification,
        "outcome_verified": outcome.verified,
        "promotion_authority": promotion_authority,
        "authority_handoff": handoff,
        "summary": "source candidate promoted under v5 correction and promotion authority",
    }
    state["last_promotion"] = promotion
    _schedule_next_auto_run(state)
    _save_state(cwd, state)
    _append_history(cwd, {"time_utc": promotion["time_utc"], "action": "promote", "generation": promotion["generation"], "changed_paths": applied})
    return {"ok": True, "promotion": promotion, "status": zero_ai_source_evolution_status(cwd)}


def zero_ai_source_evolution_rollback(cwd: str) -> dict[str, Any]:
    handoff = acknowledge_consumed_execution_ticket(cwd, "recover", max_handoff_seconds=10)
    if not bool(handoff.get("ok", False)):
        return {"ok": False, "blocked": True, "reason": "constitutional_recovery_handoff_missing", "authority": handoff, "status": zero_ai_source_evolution_status(cwd)}
    state = _load_state(cwd)
    checkpoint_id = str((state.get("last_promotion") or {}).get("checkpoint", {}).get("checkpoint_id", ""))
    if not checkpoint_id:
        checkpoint_id = str((state.get("last_canary") or {}).get("checkpoint", {}).get("checkpoint_id", ""))
    checkpoint = _load_checkpoint(cwd, checkpoint_id) if checkpoint_id else None
    if checkpoint is None:
        return {"ok": False, "blocked": True, "reason": "no guarded source evolution checkpoint is available for rollback", "status": zero_ai_source_evolution_status(cwd)}
    _restore_files(cwd, checkpoint)
    state["rollback_count"] = int(state.get("rollback_count", 0)) + 1
    state["pending_candidate"] = {}
    rollback = {"ok": True, "time_utc": _utc_now(), "checkpoint": checkpoint, "authority_handoff": handoff, "summary": "source rollback restored the last checkpoint"}
    state["last_rollback"] = rollback
    _save_state(cwd, state)
    _append_history(cwd, {"time_utc": rollback["time_utc"], "action": "rollback", "checkpoint_id": checkpoint_id})
    return {"ok": True, "rollback": rollback, "status": zero_ai_source_evolution_status(cwd)}


def zero_ai_source_evolution_auto_run(cwd: str) -> dict[str, Any]:
    state = _load_state(cwd)
    status = zero_ai_source_evolution_status(cwd)
    if not bool(status.get("auto_enabled", True)):
        return {"ok": False, "blocked": True, "reason": "guarded source evolution is disabled", "status": status}
    if not bool(status.get("due_now", False)):
        return {"ok": True, "changed": False, "reason": "guarded source evolution is not due yet", "status": status}
    simulation = zero_ai_source_evolution_simulate(cwd)
    if not bool(simulation.get("candidate_available", False)):
        _schedule_next_auto_run(state)
        _save_state(cwd, state)
        return {"ok": True, "changed": False, "reason": "no guarded source candidate is available", "simulation": simulation, "status": zero_ai_source_evolution_status(cwd)}
    if not bool(simulation.get("ready_for_canary", False)):
        return {"ok": False, "changed": False, "reason": "source candidate did not pass simulation", "simulation": simulation, "status": zero_ai_source_evolution_status(cwd)}
    canary = zero_ai_source_evolution_canary(cwd)
    if not bool(canary.get("ok", False)):
        return {"ok": False, "changed": False, "reason": "source canary failed", "simulation": simulation, "canary": canary, "status": zero_ai_source_evolution_status(cwd)}
    promotion = zero_ai_source_evolution_promote(cwd)
    if not bool(promotion.get("ok", False)):
        return {
            "ok": False,
            "changed": False,
            "reason": str(promotion.get("reason", "promotion_authority_required")),
            "simulation": simulation,
            "canary": canary,
            "promotion": promotion,
            "status": zero_ai_source_evolution_status(cwd),
        }
    return {"ok": True, "changed": True, "simulation": simulation, "canary": canary, "promotion": promotion.get("promotion", {}), "status": zero_ai_source_evolution_status(cwd)}


def zero_ai_source_evolution_generate_upgrade(cwd: str) -> dict[str, Any]:
    result = zero_ai_source_evolution_propose(cwd)
    proposal = dict(result.get("proposal") or {})
    next_action = "canary" if bool(proposal.get("candidate_available", False)) and bool(proposal.get("safe", False)) else "stabilize"
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
