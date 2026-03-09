from __future__ import annotations

import json
import re
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


def _state_default() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "allowed_scopes": [
            "src/zero_os/phase_runtime.py:_runtime_loop_default.interval_seconds",
            "src/zero_os/zero_ai_autonomy.py:_loop_state_default.interval_seconds",
        ],
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
    return state


def _save_state(cwd: str, state: dict[str, Any]) -> dict[str, Any]:
    _save_json(_state_path(cwd), state)
    return state


def _target_specs(cwd: str) -> list[dict[str, Any]]:
    return [
        {
            "key": "runtime_loop_source_default",
            "label": "Phase runtime loop default",
            "relative_path": "src/zero_os/phase_runtime.py",
            "path": str(Path(cwd).resolve() / "src" / "zero_os" / "phase_runtime.py"),
            "pattern": r'(def _runtime_loop_default\(\) -> dict:\s+return \{\s+"enabled": False,\s+"interval_seconds": )(\d+)',
            "target_key": "runtime_loop_interval_seconds",
            "test_hint": "tests.test_phase_runtime",
        },
        {
            "key": "autonomy_loop_source_default",
            "label": "Autonomy loop default",
            "relative_path": "src/zero_os/zero_ai_autonomy.py",
            "path": str(Path(cwd).resolve() / "src" / "zero_os" / "zero_ai_autonomy.py"),
            "pattern": r'(def _loop_state_default\(\) -> dict:\s+return \{\s+"enabled": False,\s+"interval_seconds": )(\d+)',
            "target_key": "autonomy_loop_interval_seconds",
            "test_hint": "tests.test_zero_ai_autonomy",
        },
    ]


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


def _proposal_from_live(cwd: str) -> dict[str, Any]:
    from zero_os.zero_ai_evolution import zero_ai_evolution_status

    evolution_status = zero_ai_evolution_status(cwd)
    ready, ready_reasons = _source_ready(evolution_status)
    current_profile = dict(evolution_status.get("current_profile") or {})
    target_profile = {
        "runtime_loop_interval_seconds": int(current_profile.get("runtime_loop_interval_seconds", 0) or 0),
        "autonomy_loop_interval_seconds": int(current_profile.get("autonomy_loop_interval_seconds", 0) or 0),
    }

    mutations: list[dict[str, Any]] = []
    missing_files: list[str] = []
    for spec in _target_specs(cwd):
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
                }
            )

    beneficial = bool(mutations)
    candidate_id = str(uuid.uuid4())[:10]
    predicted_gain = round(len(mutations) * 3.5, 2)
    summary = "learned source defaults already match the promoted runtime profile"
    if missing_files:
        summary = "source evolution is blocked because one or more allowlisted source files are missing"
    elif mutations:
        summary = "guarded source evolution candidate generated from the promoted runtime profile"
    if not ready:
        summary = "guarded source evolution is blocked until bounded evolution settles"

    verification_plan = {
        "py_compile": [item["path"] for item in mutations],
        "tests": ["tests.test_phase_runtime", "tests.test_zero_ai_autonomy", "tests.test_zero_ai_evolution"],
    }

    return {
        "ok": True,
        "candidate_id": candidate_id,
        "time_utc": _utc_now(),
        "candidate_available": bool(mutations),
        "beneficial": beneficial,
        "safe": ready and not missing_files,
        "blocked_reasons": ([] if ready else ready_reasons) + [f"missing allowlisted source file: {path}" for path in missing_files],
        "current_profile": target_profile,
        "mutations": mutations,
        "predicted_gain": predicted_gain if beneficial else 0.0,
        "summary": summary,
        "verification_plan": verification_plan,
    }


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


def _verification_commands(cwd: str, changed_paths: list[str]) -> list[list[str]]:
    commands: list[list[str]] = []
    if changed_paths:
        commands.append([sys.executable, "-m", "py_compile", *changed_paths])
    repo_root = Path(cwd).resolve()
    required_tests = [
        repo_root / "tests" / "test_phase_runtime.py",
        repo_root / "tests" / "test_zero_ai_autonomy.py",
        repo_root / "tests" / "test_zero_ai_evolution.py",
    ]
    if all(path.exists() for path in required_tests):
        commands.append([sys.executable, "-m", "unittest", "tests.test_phase_runtime", "tests.test_zero_ai_autonomy", "tests.test_zero_ai_evolution", "-q"])
    return commands


def _run_verification(cwd: str, changed_paths: list[str]) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    for command in _verification_commands(cwd, changed_paths):
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
        "current_source_generation": int(state.get("current_source_generation", 0)),
        "promoted_count": int(state.get("promoted_count", 0)),
        "rollback_count": int(state.get("rollback_count", 0)),
        "auto_enabled": bool(state.get("auto_enabled", True)),
        "min_auto_interval_seconds": int(state.get("min_auto_interval_seconds", 21600)),
        "last_auto_run_utc": str(state.get("last_auto_run_utc", "")),
        "next_auto_run_utc": str(state.get("next_auto_run_utc", "")),
        "due_now": _auto_due(state),
        "source_evolution_ready": bool(proposal.get("safe", False)),
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
    changed_paths: list[str] = []
    verification = {"ok": False, "checks": []}
    try:
        changed_paths = _apply_mutations(cwd, simulation)
        verification = _run_verification(cwd, changed_paths)
    finally:
        _restore_files(cwd, checkpoint)

    passed = bool(verification.get("ok", False))
    canary = {
        "ok": passed,
        "time_utc": _utc_now(),
        "passed": passed,
        "checkpoint": checkpoint,
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
    verification = _run_verification(cwd, applied_paths)
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
