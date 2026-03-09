from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _runtime_root(cwd: str) -> Path:
    path = Path(cwd).resolve() / ".zero_os" / "runtime"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _assistant_root(cwd: str) -> Path:
    path = Path(cwd).resolve() / ".zero_os" / "assistant"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _evolution_root(cwd: str) -> Path:
    path = Path(cwd).resolve() / ".zero_os" / "evolution"
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


def _runtime_status_path(cwd: str) -> Path:
    return _runtime_root(cwd) / "phase_runtime_status.json"


def _runtime_loop_path(cwd: str) -> Path:
    return _runtime_root(cwd) / "runtime_loop_state.json"


def _runtime_agent_path(cwd: str) -> Path:
    return _runtime_root(cwd) / "runtime_agent_state.json"


def _continuity_path(cwd: str) -> Path:
    return _runtime_root(cwd) / "zero_ai_self_continuity.json"


def _autonomy_loop_path(cwd: str) -> Path:
    return _assistant_root(cwd) / "autonomy_loop_state.json"


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


def _runtime_loop_default() -> dict[str, Any]:
    return {
        "enabled": False,
        "interval_seconds": 180,
        "last_run_utc": "",
        "next_run_utc": "",
    }


def _autonomy_loop_default() -> dict[str, Any]:
    return {
        "enabled": False,
        "interval_seconds": 300,
        "last_run_utc": "",
        "next_run_utc": "",
    }


def _continuity_default() -> dict[str, Any]:
    return {
        "continuity": {
            "continuity_score": 0.0,
            "same_system": False,
        },
        "contradiction_detection": {
            "has_contradiction": True,
            "issues": ["missing_continuity_state"],
        },
    }


def _runtime_status_default() -> dict[str, Any]:
    return {
        "ok": False,
        "missing": True,
        "runtime_ready": False,
        "runtime_score": 0.0,
    }


def _state_default() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "allowed_scopes": [
            "runtime_loop.interval_seconds",
            "autonomy_loop.interval_seconds",
        ],
        "safe_bounds": {
            "runtime_loop": {"min": 120, "max": 300},
            "autonomy_loop": {"min": 180, "max": 420},
        },
        "targets": {
            "stable": {
                "runtime_loop_interval_seconds": 240,
                "autonomy_loop_interval_seconds": 360,
            },
            "recovery": {
                "runtime_loop_interval_seconds": 120,
                "autonomy_loop_interval_seconds": 180,
            },
        },
        "current_generation": 0,
        "promoted_count": 0,
        "rollback_count": 0,
        "auto_enabled": True,
        "min_auto_interval_seconds": 3600,
        "last_auto_run_utc": "",
        "next_auto_run_utc": "",
        "active_profile": {},
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


def _parse_utc(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _runtime_snapshot(cwd: str) -> dict[str, Any]:
    runtime_status = _load_json(_runtime_status_path(cwd), _runtime_status_default())
    runtime_loop = _load_json(_runtime_loop_path(cwd), _runtime_loop_default())
    runtime_agent = _load_json(_runtime_agent_path(cwd), {"installed": False, "running": False, "last_failure": ""})
    autonomy_loop = _load_json(_autonomy_loop_path(cwd), _autonomy_loop_default())
    continuity = _load_json(_continuity_path(cwd), _continuity_default())

    continuity_data = continuity.get("continuity", {})
    contradiction = continuity.get("contradiction_detection", {})
    continuity_healthy = bool(continuity_data.get("same_system", False)) and not bool(contradiction.get("has_contradiction", False))
    runtime_ready = bool(runtime_status.get("runtime_ready", False))

    stable_mode = continuity_healthy and runtime_ready and bool(runtime_agent.get("running", False))
    profile = {
        "runtime_loop_interval_seconds": int(runtime_loop.get("interval_seconds", 180) or 180),
        "autonomy_loop_interval_seconds": int(autonomy_loop.get("interval_seconds", 300) or 300),
        "runtime_loop_enabled": bool(runtime_loop.get("enabled", False)),
        "autonomy_loop_enabled": bool(autonomy_loop.get("enabled", False)),
        "background_agent_running": bool(runtime_agent.get("running", False)),
        "background_agent_installed": bool(runtime_agent.get("installed", False)),
        "runtime_ready": runtime_ready,
        "runtime_score": float(runtime_status.get("runtime_score", 0.0) or 0.0),
        "continuity_score": float(continuity_data.get("continuity_score", 0.0) or 0.0),
        "continuity_healthy": continuity_healthy,
        "same_system": bool(continuity_data.get("same_system", False)),
        "has_contradiction": bool(contradiction.get("has_contradiction", False)),
        "runtime_last_failure": str(runtime_loop.get("last_failure", "") or runtime_agent.get("last_failure", "")),
        "mode": "stable" if stable_mode else "recovery",
    }
    return {
        "runtime_status": runtime_status,
        "runtime_loop": runtime_loop,
        "runtime_agent": runtime_agent,
        "autonomy_loop": autonomy_loop,
        "continuity": continuity,
        "profile": profile,
    }


def _current_targets(state: dict[str, Any], snapshot: dict[str, Any]) -> dict[str, int]:
    mode = str(snapshot.get("profile", {}).get("mode", "recovery"))
    targets = dict((state.get("targets", {}) or {}).get(mode, {}))
    if not targets:
        targets = dict((state.get("targets", {}) or {}).get("stable", {}))
    return {
        "runtime_loop_interval_seconds": int(targets.get("runtime_loop_interval_seconds", 240)),
        "autonomy_loop_interval_seconds": int(targets.get("autonomy_loop_interval_seconds", 360)),
    }


def _interval_fit(value: int, target: int, min_value: int, max_value: int) -> float:
    span = max(1, max_value - min_value)
    distance = abs(int(value) - int(target))
    return max(0.0, 1.0 - (distance / span))


def _fitness(snapshot: dict[str, Any], state: dict[str, Any], profile_override: dict[str, Any] | None = None) -> dict[str, Any]:
    profile = dict(snapshot.get("profile", {}))
    if profile_override:
        profile.update(profile_override)
    bounds = state.get("safe_bounds", {})
    targets = _current_targets(state, {"profile": profile})

    runtime_fit = _interval_fit(
        int(profile.get("runtime_loop_interval_seconds", 180) or 180),
        targets["runtime_loop_interval_seconds"],
        int((bounds.get("runtime_loop", {}) or {}).get("min", 120)),
        int((bounds.get("runtime_loop", {}) or {}).get("max", 300)),
    )
    autonomy_fit = _interval_fit(
        int(profile.get("autonomy_loop_interval_seconds", 300) or 300),
        targets["autonomy_loop_interval_seconds"],
        int((bounds.get("autonomy_loop", {}) or {}).get("min", 180)),
        int((bounds.get("autonomy_loop", {}) or {}).get("max", 420)),
    )

    components = {
        "continuity_health": 30.0 if bool(profile.get("continuity_healthy", False)) else 0.0,
        "runtime_ready": 25.0 if bool(profile.get("runtime_ready", False)) else 0.0,
        "background_agent": 15.0 if bool(profile.get("background_agent_running", False)) else 0.0,
        "runtime_loop_enabled": 10.0 if bool(profile.get("runtime_loop_enabled", False)) else 0.0,
        "autonomy_loop_enabled": 10.0 if bool(profile.get("autonomy_loop_enabled", False)) else 0.0,
        "runtime_interval_fit": round(runtime_fit * 5.0, 2),
        "autonomy_interval_fit": round(autonomy_fit * 5.0, 2),
    }
    fitness_score = round(sum(components.values()), 2)
    return {
        "fitness_score": fitness_score,
        "components": components,
        "targets": targets,
        "mode": str(profile.get("mode", "recovery")),
    }


def _auto_due(state: dict[str, Any]) -> bool:
    if not bool(state.get("auto_enabled", True)):
        return False
    next_run = _parse_utc(str(state.get("next_auto_run_utc", "")))
    if next_run is None:
        return True
    return datetime.now(timezone.utc) >= next_run


def _schedule_next_auto_run(state: dict[str, Any]) -> None:
    interval = max(300, min(86400, int(state.get("min_auto_interval_seconds", 3600) or 3600)))
    state["last_auto_run_utc"] = _utc_now()
    state["next_auto_run_utc"] = (datetime.now(timezone.utc) + timedelta(seconds=interval)).isoformat()


def _bounded_ready(snapshot: dict[str, Any]) -> tuple[bool, list[str]]:
    profile = snapshot.get("profile", {})
    reasons: list[str] = []
    if not bool(profile.get("same_system", False)):
        reasons.append("identity continuity is not stable enough for self evolution")
    if bool(profile.get("has_contradiction", False)):
        reasons.append("active self contradiction blocks self evolution")
    if not bool(profile.get("background_agent_running", False)):
        reasons.append("background agent should be running before autonomous self evolution")
    if not bool(profile.get("runtime_loop_enabled", False)):
        reasons.append("runtime loop should be enabled before self evolution")
    if not bool(profile.get("autonomy_loop_enabled", False)):
        reasons.append("autonomy loop should be enabled before self evolution")
    return (len(reasons) == 0, reasons)


def _proposal_from_live(cwd: str) -> dict[str, Any]:
    state = _load_state(cwd)
    snapshot = _runtime_snapshot(cwd)
    ready, ready_reasons = _bounded_ready(snapshot)
    targets = _current_targets(state, snapshot)
    current = snapshot.get("profile", {})
    changes: list[dict[str, Any]] = []

    for key, scope in (
        ("runtime_loop_interval_seconds", "runtime_loop.interval_seconds"),
        ("autonomy_loop_interval_seconds", "autonomy_loop.interval_seconds"),
    ):
        current_value = int(current.get(key, 0) or 0)
        target_value = int(targets.get(key, current_value) or current_value)
        if current_value != target_value:
            changes.append(
                {
                    "scope": scope,
                    "from": current_value,
                    "to": target_value,
                }
            )

    current_fitness = _fitness(snapshot, state)
    proposed_fitness = _fitness(snapshot, state, profile_override=targets)
    beneficial = proposed_fitness["fitness_score"] > current_fitness["fitness_score"]
    candidate_id = str(uuid.uuid4())[:10]
    proposal = {
        "ok": True,
        "candidate_id": candidate_id,
        "time_utc": _utc_now(),
        "candidate_available": bool(changes),
        "beneficial": beneficial,
        "safe": ready,
        "blocked_reasons": [] if ready else ready_reasons,
        "mode": str(current.get("mode", "recovery")),
        "current_profile": {
            "runtime_loop_interval_seconds": int(current.get("runtime_loop_interval_seconds", 180) or 180),
            "autonomy_loop_interval_seconds": int(current.get("autonomy_loop_interval_seconds", 300) or 300),
        },
        "target_profile": targets,
        "mutations": changes,
        "baseline_fitness": current_fitness,
        "candidate_fitness": proposed_fitness,
        "predicted_gain": round(proposed_fitness["fitness_score"] - current_fitness["fitness_score"], 2),
        "summary": "bounded loop tuning candidate generated" if changes else "current bounded profile already aligned",
    }
    if not ready:
        proposal["summary"] = "bounded self evolution blocked until the live system is stable"
    elif changes and not beneficial:
        proposal["summary"] = "candidate was generated but would not measurably improve bounded fitness"
    return proposal


def _write_loop_interval(path: Path, default: dict[str, Any], interval_seconds: int) -> None:
    payload = _load_json(path, default)
    payload["interval_seconds"] = int(interval_seconds)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _apply_profile(cwd: str, profile: dict[str, Any]) -> None:
    _write_loop_interval(
        _runtime_loop_path(cwd),
        _runtime_loop_default(),
        int(profile.get("runtime_loop_interval_seconds", 180) or 180),
    )
    _write_loop_interval(
        _autonomy_loop_path(cwd),
        _autonomy_loop_default(),
        int(profile.get("autonomy_loop_interval_seconds", 300) or 300),
    )


def _create_checkpoint(cwd: str, kind: str, baseline_profile: dict[str, Any], proposal: dict[str, Any]) -> dict[str, Any]:
    checkpoint_id = f"{kind}_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}_{str(uuid.uuid4())[:6]}"
    payload = {
        "checkpoint_id": checkpoint_id,
        "created_utc": _utc_now(),
        "kind": kind,
        "baseline_profile": baseline_profile,
        "proposal": proposal,
    }
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
    if not isinstance(payload, dict):
        return None
    payload["path"] = str(path)
    return payload


def zero_ai_evolution_status(cwd: str) -> dict[str, Any]:
    state = _load_state(cwd)
    snapshot = _runtime_snapshot(cwd)
    current_fitness = _fitness(snapshot, state)
    proposal = _proposal_from_live(cwd)
    ready, ready_reasons = _bounded_ready(snapshot)
    pending_candidate = dict(state.get("pending_candidate") or {})
    recommended_action = "observe"
    if pending_candidate and bool((state.get("last_canary") or {}).get("passed", False)):
        recommended_action = "promote"
    elif proposal.get("candidate_available", False) and proposal.get("beneficial", False) and ready and _auto_due(state):
        recommended_action = "auto_run"

    status = {
        "ok": True,
        "time_utc": _utc_now(),
        "engine_path": str(_state_path(cwd)),
        "history_path": str(_history_path(cwd)),
        "checkpoint_root": str(_checkpoint_root(cwd)),
        "allowed_scopes": state.get("allowed_scopes", []),
        "safe_bounds": state.get("safe_bounds", {}),
        "targets": state.get("targets", {}),
        "current_generation": int(state.get("current_generation", 0)),
        "promoted_count": int(state.get("promoted_count", 0)),
        "rollback_count": int(state.get("rollback_count", 0)),
        "auto_enabled": bool(state.get("auto_enabled", True)),
        "min_auto_interval_seconds": int(state.get("min_auto_interval_seconds", 3600)),
        "last_auto_run_utc": str(state.get("last_auto_run_utc", "")),
        "next_auto_run_utc": str(state.get("next_auto_run_utc", "")),
        "due_now": _auto_due(state),
        "self_evolution_ready": ready,
        "blocked_reasons": ready_reasons,
        "recommended_action": recommended_action,
        "current_profile": {
            "runtime_loop_interval_seconds": snapshot["profile"]["runtime_loop_interval_seconds"],
            "autonomy_loop_interval_seconds": snapshot["profile"]["autonomy_loop_interval_seconds"],
        },
        "live_health": {
            "runtime_ready": snapshot["profile"]["runtime_ready"],
            "runtime_score": snapshot["profile"]["runtime_score"],
            "continuity_healthy": snapshot["profile"]["continuity_healthy"],
            "continuity_score": snapshot["profile"]["continuity_score"],
            "background_agent_running": snapshot["profile"]["background_agent_running"],
            "runtime_loop_enabled": snapshot["profile"]["runtime_loop_enabled"],
            "autonomy_loop_enabled": snapshot["profile"]["autonomy_loop_enabled"],
            "mode": snapshot["profile"]["mode"],
        },
        "fitness": current_fitness,
        "proposal": proposal,
        "pending_candidate": pending_candidate,
        "last_proposal": dict(state.get("last_proposal") or {}),
        "last_simulation": dict(state.get("last_simulation") or {}),
        "last_canary": dict(state.get("last_canary") or {}),
        "last_promotion": dict(state.get("last_promotion") or {}),
        "last_rollback": dict(state.get("last_rollback") or {}),
        "recent_history": _history_tail(cwd, limit=8),
    }
    state["active_profile"] = status["current_profile"]
    _save_state(cwd, state)
    return status


def zero_ai_evolution_propose(cwd: str) -> dict[str, Any]:
    state = _load_state(cwd)
    proposal = _proposal_from_live(cwd)
    state["last_proposal"] = proposal
    state["active_profile"] = dict(proposal.get("current_profile") or {})
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
    return {
        "ok": True,
        "proposal": proposal,
        "status": zero_ai_evolution_status(cwd),
    }


def zero_ai_evolution_simulate(cwd: str) -> dict[str, Any]:
    state = _load_state(cwd)
    proposal = _proposal_from_live(cwd)
    simulation = {
        "ok": True,
        "time_utc": _utc_now(),
        "candidate_id": proposal.get("candidate_id", ""),
        "candidate_available": proposal.get("candidate_available", False),
        "safe": bool(proposal.get("safe", False)),
        "beneficial": bool(proposal.get("beneficial", False)),
        "blocked_reasons": list(proposal.get("blocked_reasons", [])),
        "current_profile": proposal.get("current_profile", {}),
        "target_profile": proposal.get("target_profile", {}),
        "mutations": proposal.get("mutations", []),
        "baseline_fitness": proposal.get("baseline_fitness", {}),
        "candidate_fitness": proposal.get("candidate_fitness", {}),
        "predicted_gain": proposal.get("predicted_gain", 0.0),
        "summary": proposal.get("summary", ""),
        "ready_for_canary": bool(proposal.get("candidate_available", False))
        and bool(proposal.get("safe", False))
        and bool(proposal.get("beneficial", False)),
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


def zero_ai_evolution_canary(cwd: str) -> dict[str, Any]:
    state = _load_state(cwd)
    simulation = zero_ai_evolution_simulate(cwd)
    if not bool(simulation.get("ready_for_canary", False)):
        report = {
            "ok": False,
            "blocked": True,
            "reason": "bounded evolution candidate is not ready for canary",
            "simulation": simulation,
        }
        state["last_canary"] = report
        _save_state(cwd, state)
        return report

    baseline_profile = dict(simulation.get("current_profile") or {})
    target_profile = dict(simulation.get("target_profile") or {})
    checkpoint = _create_checkpoint(cwd, "canary", baseline_profile, simulation)
    _apply_profile(cwd, target_profile)

    from zero_os.self_continuity import zero_ai_self_continuity_update

    continuity = zero_ai_self_continuity_update(cwd)
    snapshot_after = _runtime_snapshot(cwd)
    observed_fitness = _fitness(snapshot_after, state)
    passed = (
        bool(snapshot_after["profile"].get("continuity_healthy", False))
        and bool(snapshot_after["profile"].get("same_system", False))
        and observed_fitness["fitness_score"] >= float((simulation.get("candidate_fitness") or {}).get("fitness_score", 0.0))
    )
    _apply_profile(cwd, baseline_profile)

    canary = {
        "ok": passed,
        "time_utc": _utc_now(),
        "passed": passed,
        "checkpoint": checkpoint,
        "baseline_profile": baseline_profile,
        "candidate_profile": target_profile,
        "simulation": simulation,
        "observed_fitness": observed_fitness,
        "continuity_score": float((continuity.get("continuity") or {}).get("continuity_score", 0.0) or 0.0),
        "same_system": bool((continuity.get("continuity") or {}).get("same_system", False)),
        "has_contradiction": bool((continuity.get("contradiction_detection") or {}).get("has_contradiction", False)),
        "summary": "candidate passed canary and is ready for promotion" if passed else "candidate failed canary and was not promoted",
    }
    if passed:
        state["pending_candidate"] = {
            "candidate_id": str(simulation.get("candidate_id", "")),
            "candidate_profile": target_profile,
            "checkpoint_id": checkpoint["checkpoint_id"],
            "baseline_profile": baseline_profile,
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
            "candidate_id": simulation.get("candidate_id", ""),
            "observed_fitness": observed_fitness.get("fitness_score"),
        },
    )
    return canary


def zero_ai_evolution_promote(cwd: str) -> dict[str, Any]:
    state = _load_state(cwd)
    pending = dict(state.get("pending_candidate") or {})
    last_canary = dict(state.get("last_canary") or {})
    if not pending or not bool(last_canary.get("passed", False)):
        return {
            "ok": False,
            "blocked": True,
            "reason": "no successful canary candidate is waiting for promotion",
            "status": zero_ai_evolution_status(cwd),
        }

    candidate_profile = dict(pending.get("candidate_profile") or {})
    baseline_profile = dict(pending.get("baseline_profile") or {})
    promotion_checkpoint = _create_checkpoint(cwd, "promotion", baseline_profile, last_canary)
    _apply_profile(cwd, candidate_profile)

    state["current_generation"] = int(state.get("current_generation", 0)) + 1
    state["promoted_count"] = int(state.get("promoted_count", 0)) + 1
    state["active_profile"] = candidate_profile
    state["pending_candidate"] = {}
    promotion = {
        "ok": True,
        "time_utc": _utc_now(),
        "generation": state["current_generation"],
        "candidate_profile": candidate_profile,
        "baseline_profile": baseline_profile,
        "checkpoint": promotion_checkpoint,
        "summary": "bounded evolution candidate promoted",
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
            "candidate_profile": candidate_profile,
        },
    )
    return {
        "ok": True,
        "promotion": promotion,
        "status": zero_ai_evolution_status(cwd),
    }


def zero_ai_evolution_rollback(cwd: str) -> dict[str, Any]:
    state = _load_state(cwd)
    checkpoint_id = str((state.get("last_promotion") or {}).get("checkpoint", {}).get("checkpoint_id", ""))
    if not checkpoint_id:
        checkpoint_id = str((state.get("last_canary") or {}).get("checkpoint", {}).get("checkpoint_id", ""))
    if not checkpoint_id:
        return {
            "ok": False,
            "blocked": True,
            "reason": "no evolution checkpoint available for rollback",
            "status": zero_ai_evolution_status(cwd),
        }

    checkpoint = _load_checkpoint(cwd, checkpoint_id)
    if checkpoint is None:
        return {
            "ok": False,
            "blocked": True,
            "reason": f"evolution checkpoint not found: {checkpoint_id}",
            "status": zero_ai_evolution_status(cwd),
        }

    baseline_profile = dict(checkpoint.get("baseline_profile") or {})
    _apply_profile(cwd, baseline_profile)
    state["rollback_count"] = int(state.get("rollback_count", 0)) + 1
    state["pending_candidate"] = {}
    rollback = {
        "ok": True,
        "time_utc": _utc_now(),
        "checkpoint": checkpoint,
        "restored_profile": baseline_profile,
        "summary": "bounded evolution rollback restored the last checkpoint",
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
    return {
        "ok": True,
        "rollback": rollback,
        "status": zero_ai_evolution_status(cwd),
    }


def zero_ai_evolution_auto_run(cwd: str) -> dict[str, Any]:
    state = _load_state(cwd)
    status_before = zero_ai_evolution_status(cwd)
    if not bool(status_before.get("auto_enabled", True)):
        return {
            "ok": False,
            "blocked": True,
            "reason": "bounded self evolution is disabled",
            "status": status_before,
        }
    if not bool(status_before.get("due_now", False)):
        return {
            "ok": True,
            "changed": False,
            "reason": "bounded self evolution is not due yet",
            "status": status_before,
        }

    simulation = zero_ai_evolution_simulate(cwd)
    if not bool(simulation.get("candidate_available", False)):
        _schedule_next_auto_run(state)
        _save_state(cwd, state)
        return {
            "ok": True,
            "changed": False,
            "reason": "no bounded candidate available right now",
            "simulation": simulation,
            "status": zero_ai_evolution_status(cwd),
        }
    if not bool(simulation.get("ready_for_canary", False)):
        _schedule_next_auto_run(state)
        _save_state(cwd, state)
        return {
            "ok": False,
            "changed": False,
            "reason": "bounded self evolution candidate did not pass simulation",
            "simulation": simulation,
            "status": zero_ai_evolution_status(cwd),
        }

    canary = zero_ai_evolution_canary(cwd)
    if not bool(canary.get("ok", False)):
        _schedule_next_auto_run(state)
        _save_state(cwd, state)
        return {
            "ok": False,
            "changed": False,
            "reason": "bounded self evolution canary failed",
            "simulation": simulation,
            "canary": canary,
            "status": zero_ai_evolution_status(cwd),
        }

    promotion = zero_ai_evolution_promote(cwd)
    return {
        "ok": bool(promotion.get("ok", False)),
        "changed": bool(promotion.get("ok", False)),
        "simulation": simulation,
        "canary": canary,
        "promotion": promotion.get("promotion", {}),
        "status": zero_ai_evolution_status(cwd),
    }
