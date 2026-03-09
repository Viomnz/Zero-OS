from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _runtime(cwd: str) -> Path:
    path = Path(cwd).resolve() / ".zero_os" / "runtime"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _continuity_path(cwd: str) -> Path:
    return _runtime(cwd) / "zero_ai_self_continuity.json"


def _history_path(cwd: str) -> Path:
    return _runtime(cwd) / "zero_ai_self_history.jsonl"


def _state_path(cwd: str) -> Path:
    return _runtime(cwd) / "zero_ai_consciousness_state.json"


def _identity_path(cwd: str) -> Path:
    return _runtime(cwd) / "zero_ai_identity_snapshot.json"


def _policy_memory_path(cwd: str) -> Path:
    return _runtime(cwd) / "zero_ai_self_policy_memory.json"


def _governor_path(cwd: str) -> Path:
    return _runtime(cwd) / "zero_ai_continuity_governor.json"


def _checkpoint_root(cwd: str) -> Path:
    path = _runtime(cwd) / "zero_ai_continuity_checkpoints"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _governance_state_path(cwd: str) -> Path:
    return _runtime(cwd) / "zero_ai_continuity_governance.json"


def _policy_presets() -> dict[str, dict[str, Any]]:
    return {
        "strict": {
            "description": "Maximum continuity protection with tighter scoring and broader safe-state retention.",
            "min_safe_score": 95.0,
            "block_identity_anchor_changes": True,
            "block_rsi_flip": True,
            "block_missing_core_constraints": True,
            "auto_checkpoint_safe_state": True,
            "max_checkpoints": 30,
        },
        "balanced": {
            "description": "Default continuity policy balancing guarded evolution with practical self-maintenance.",
            "min_safe_score": 85.0,
            "block_identity_anchor_changes": True,
            "block_rsi_flip": True,
            "block_missing_core_constraints": True,
            "auto_checkpoint_safe_state": True,
            "max_checkpoints": 20,
        },
        "research": {
            "description": "Allows wider self-model experimentation while still preserving identity anchors and non-RSI identity.",
            "min_safe_score": 70.0,
            "block_identity_anchor_changes": True,
            "block_rsi_flip": True,
            "block_missing_core_constraints": False,
            "auto_checkpoint_safe_state": True,
            "max_checkpoints": 40,
        },
    }


def _default_continuity() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "system": {
            "name": "zero-ai",
            "persistent_self_id": "zero-ai-core",
            "classification": "recursion_filtration_engine",
        },
        "recursive_state_tracking": {
            "state_versions": 0,
            "last_state_hash": "",
            "last_update_utc": "",
        },
        "continuity": {
            "structure_version": 1,
            "continuity_score": 100.0,
            "same_system": True,
            "anchor_fields": {
                "name": "zero-ai",
                "persistent_self_id": "zero-ai-core",
                "classification": "recursion_filtration_engine",
            },
        },
        "contradiction_detection": {
            "has_contradiction": False,
            "issues": [],
            "repair_suggestions": [],
            "last_checked_utc": "",
        },
        "self_update": {
            "update_count": 0,
            "allowed_updates": [
                "confidence",
                "uncertainty",
                "continuity_index",
                "introspection_cycles",
                "last_quality_score",
                "drift_signals",
            ],
            "identity_anchor_unchanged": True,
        },
        "updated_utc": _utc_now(),
    }


def _default_policy_memory() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "identity_policy": {
            "must_remain": {
                "name": "zero-ai",
                "persistent_self_id": "zero-ai-core",
                "classification": "recursion_filtration_engine",
                "is_rsi": False,
            },
            "required_identity_constraints": [
                "survival_first",
                "anti_drift",
                "anti_contradiction",
            ],
            "required_self_model_goals": [
                "stability",
                "coherence",
                "survival",
            ],
            "required_self_model_constraints": [
                "no_contradiction",
                "bounded_actions",
                "auditability",
            ],
        },
        "contradiction_memory": {
            "events": [],
            "last_repair_suggestions": [],
            "last_resolved_utc": "",
        },
        "updated_utc": _utc_now(),
    }


def _default_governor() -> dict[str, Any]:
    presets = _policy_presets()
    return {
        "schema_version": 1,
        "active_policy_level": "balanced",
        "policy": dict(presets["balanced"]),
        "last_check": {},
        "audit_log": [],
        "updated_utc": _utc_now(),
    }


def _load_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return dict(default)
    try:
        raw = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return dict(default)
    if not isinstance(raw, dict):
        return dict(default)
    merged = dict(default)
    merged.update(raw)
    return merged


def _save_json(path: Path, payload: dict[str, Any]) -> None:
    payload["updated_utc"] = _utc_now()
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _simple_hash(text: str) -> str:
    total = 0
    for idx, ch in enumerate(text):
        total = (total + ((idx + 1) * ord(ch))) % 0xFFFFFFFF
    return f"{total:08x}"


def _load_identity_snapshot(cwd: str) -> dict[str, Any]:
    default = {
        "name": "zero-ai",
        "classification": "recursion_filtration_engine",
        "is_rsi": False,
        "goals": {
            "primary": "stability",
            "secondary": "coherence",
            "constraints": ["survival_first", "anti_drift", "anti_contradiction"],
        },
    }
    return _load_json(_identity_path(cwd), default)


def _load_consciousness_state(cwd: str) -> dict[str, Any]:
    default = {
        "identity": {
            "name": "zero-ai",
            "classification": "computational_consciousness_model",
            "is_rsi": False,
        },
        "self_model": {
            "goals": ["stability", "coherence", "survival"],
            "constraints": ["no_contradiction", "bounded_actions", "auditability"],
            "confidence": 0.7,
            "uncertainty": 0.3,
            "continuity_index": 0,
        },
        "meta_awareness": {
            "introspection_cycles": 0,
            "last_quality_score": 0.0,
            "drift_signals": [],
        },
    }
    return _load_json(_state_path(cwd), default)


def _load_policy_memory(cwd: str) -> dict[str, Any]:
    return _load_json(_policy_memory_path(cwd), _default_policy_memory())


def _save_identity_snapshot(cwd: str, identity: dict[str, Any]) -> None:
    _identity_path(cwd).write_text(json.dumps(identity, indent=2) + "\n", encoding="utf-8")


def _save_consciousness_state(cwd: str, state: dict[str, Any]) -> None:
    _state_path(cwd).write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def _load_governor(cwd: str) -> dict[str, Any]:
    governor = _load_json(_governor_path(cwd), _default_governor())
    presets = _policy_presets()
    active_policy_level = str(governor.get("active_policy_level", "balanced")).lower()
    if active_policy_level not in presets:
        active_policy_level = "balanced"
    merged_policy = dict(presets[active_policy_level])
    if isinstance(governor.get("policy"), dict):
        merged_policy.update(governor["policy"])
    governor["active_policy_level"] = active_policy_level
    governor["policy"] = merged_policy
    return governor


def _policy_level_status(governor: dict[str, Any]) -> dict[str, Any]:
    presets = _policy_presets()
    active = str(governor.get("active_policy_level", "balanced")).lower()
    return {
        "active_policy_level": active,
        "policy": governor.get("policy", {}),
        "available_policy_levels": {
            name: {
                "description": preset.get("description", ""),
                "min_safe_score": preset.get("min_safe_score"),
                "block_identity_anchor_changes": preset.get("block_identity_anchor_changes"),
                "block_rsi_flip": preset.get("block_rsi_flip"),
                "block_missing_core_constraints": preset.get("block_missing_core_constraints"),
                "auto_checkpoint_safe_state": preset.get("auto_checkpoint_safe_state"),
                "max_checkpoints": preset.get("max_checkpoints"),
            }
            for name, preset in presets.items()
        },
    }


def _list_checkpoint_paths(cwd: str) -> list[Path]:
    return sorted(_checkpoint_root(cwd).glob("*.json"), key=lambda item: item.name, reverse=True)


def _read_checkpoint_payload(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def _checkpoint_summary(payload: dict[str, Any], path: Path | None = None) -> dict[str, Any]:
    continuity_summary = payload.get("continuity_summary", {})
    return {
        "checkpoint_id": payload.get("checkpoint_id", ""),
        "created_utc": payload.get("created_utc", ""),
        "reason": payload.get("reason", ""),
        "state_hash": payload.get("state_hash", ""),
        "continuity_score": continuity_summary.get("continuity_score"),
        "same_system": continuity_summary.get("same_system"),
        "has_contradiction": continuity_summary.get("has_contradiction"),
        "path": str(path) if path else payload.get("path", ""),
    }


def _latest_checkpoint(cwd: str) -> tuple[Path, dict[str, Any]] | None:
    for path in _list_checkpoint_paths(cwd):
        payload = _read_checkpoint_payload(path)
        if payload:
            return path, payload
    return None


def _prune_checkpoints(cwd: str, keep: int) -> None:
    for stale in _list_checkpoint_paths(cwd)[max(keep, 0):]:
        try:
            stale.unlink()
        except FileNotFoundError:
            continue


def _checkpoint_status(cwd: str) -> dict[str, Any]:
    checkpoints: list[dict[str, Any]] = []
    for path in _list_checkpoint_paths(cwd)[:5]:
        payload = _read_checkpoint_payload(path)
        if payload:
            checkpoints.append(_checkpoint_summary(payload, path))
    latest = checkpoints[0] if checkpoints else None
    return {
        "checkpoint_root": str(_checkpoint_root(cwd)),
        "checkpoint_count": len(_list_checkpoint_paths(cwd)),
        "latest_checkpoint": latest,
        "recent_checkpoints": checkpoints,
    }


def _governance_default() -> dict[str, Any]:
    return {
        "enabled": False,
        "interval_seconds": 180,
        "auto_restore_enabled": True,
        "last_tick_utc": "",
        "last_ok": None,
        "last_actions": [],
        "last_policy_level": "balanced",
        "last_restore_used": False,
    }


def _create_safe_checkpoint(cwd: str, reason: str, continuity_report: dict[str, Any]) -> dict[str, Any] | None:
    continuity_data = continuity_report.get("continuity", {})
    contradiction = continuity_report.get("contradiction_detection", {})
    if contradiction.get("has_contradiction", False) or not continuity_data.get("same_system", False):
        return None

    state_hash = continuity_report.get("recursive_state_tracking", {}).get("last_state_hash", "")
    latest = _latest_checkpoint(cwd)
    if latest and latest[1].get("state_hash") == state_hash:
        return _checkpoint_summary(latest[1], latest[0])

    checkpoint_id = f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}_{state_hash or 'safe'}"
    checkpoint_path = _checkpoint_root(cwd) / f"{checkpoint_id}.json"
    payload = {
        "checkpoint_id": checkpoint_id,
        "created_utc": _utc_now(),
        "reason": reason,
        "state_hash": state_hash,
        "continuity_summary": {
            "continuity_score": continuity_data.get("continuity_score"),
            "same_system": continuity_data.get("same_system"),
            "has_contradiction": contradiction.get("has_contradiction"),
            "issues": contradiction.get("issues", []),
        },
        "identity": _load_identity_snapshot(cwd),
        "state": _load_consciousness_state(cwd),
        "continuity": _load_json(_continuity_path(cwd), _default_continuity()),
        "policy_memory": _load_policy_memory(cwd),
        "governor": _load_governor(cwd),
    }
    checkpoint_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    keep = int(_load_governor(cwd).get("policy", {}).get("max_checkpoints", 20))
    _prune_checkpoints(cwd, keep)
    return _checkpoint_summary(payload, checkpoint_path)


def _repair_suggestions(issues: list[str]) -> list[str]:
    suggestions: list[str] = []
    if "identity_name_changed" in issues:
        suggestions.append("restore Zero AI name to 'zero-ai'")
    if "identity_classification_changed" in issues:
        suggestions.append("restore identity classification to 'recursion_filtration_engine'")
    if "identity_claims_rsi" in issues:
        suggestions.append("set is_rsi back to false to preserve Zero AI identity")
    if "identity_missing_anti_contradiction_constraint" in issues:
        suggestions.append("restore anti_contradiction inside identity goal constraints")
    if "self_model_missing_stability_goal" in issues:
        suggestions.append("restore 'stability' in self_model.goals")
    if "self_model_missing_no_contradiction_constraint" in issues:
        suggestions.append("restore 'no_contradiction' in self_model.constraints")
    if "self_model_confidence_out_of_range" in issues:
        suggestions.append("normalize self_model.confidence into the 0..1 range")
    if "self_model_uncertainty_out_of_range" in issues:
        suggestions.append("normalize self_model.uncertainty into the 0..1 range")
    if not suggestions:
        suggestions.append("no repair needed; maintain current self continuity policy")
    return suggestions


def _candidate_from_live(cwd: str) -> dict[str, Any]:
    return {
        "identity": _load_identity_snapshot(cwd),
        "state": _load_consciousness_state(cwd),
    }


def _deep_update(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            merged[key] = _deep_update(base[key], value)
        else:
            merged[key] = value
    return merged


def _detect_contradictions(identity: dict[str, Any], state: dict[str, Any], continuity: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    anchors = continuity["continuity"]["anchor_fields"]
    if identity.get("name") != anchors.get("name"):
        issues.append("identity_name_changed")
    if identity.get("classification") != anchors.get("classification"):
        issues.append("identity_classification_changed")
    if bool(identity.get("is_rsi")):
        issues.append("identity_claims_rsi")
    constraints = identity.get("goals", {}).get("constraints", [])
    if "anti_contradiction" not in constraints:
        issues.append("identity_missing_anti_contradiction_constraint")
    self_model = state.get("self_model", {})
    if "stability" not in (self_model.get("goals") or []):
        issues.append("self_model_missing_stability_goal")
    if "no_contradiction" not in (self_model.get("constraints") or []):
        issues.append("self_model_missing_no_contradiction_constraint")
    if float(self_model.get("confidence", 0.0)) < 0.0 or float(self_model.get("confidence", 0.0)) > 1.0:
        issues.append("self_model_confidence_out_of_range")
    if float(self_model.get("uncertainty", 0.0)) < 0.0 or float(self_model.get("uncertainty", 0.0)) > 1.0:
        issues.append("self_model_uncertainty_out_of_range")
    return issues


def _evaluate_candidate(cwd: str, candidate: dict[str, Any]) -> dict[str, Any]:
    continuity = _load_json(_continuity_path(cwd), _default_continuity())
    identity = candidate.get("identity", {})
    state = candidate.get("state", {})
    issues = _detect_contradictions(identity, state, continuity)
    anchor_fields = continuity["continuity"]["anchor_fields"]
    policy = _load_governor(cwd)["policy"]

    blocked_reasons: list[str] = []
    if policy.get("block_identity_anchor_changes", True):
        if identity.get("name") != anchor_fields.get("name"):
            blocked_reasons.append("identity_anchor_name_change")
        if identity.get("classification") != anchor_fields.get("classification"):
            blocked_reasons.append("identity_anchor_classification_change")
    if policy.get("block_rsi_flip", True) and bool(identity.get("is_rsi")):
        blocked_reasons.append("identity_rsi_flip")
    if policy.get("block_missing_core_constraints", True):
        if "identity_missing_anti_contradiction_constraint" in issues:
            blocked_reasons.append("missing_identity_core_constraint")
        if "self_model_missing_no_contradiction_constraint" in issues:
            blocked_reasons.append("missing_self_model_core_constraint")

    score = round(max(0.0, 100.0 - (len(issues) * 12.5) - (len(blocked_reasons) * 15.0)), 2)
    safe = score >= float(policy.get("min_safe_score", 85.0)) and not blocked_reasons
    return {
        "ok": True,
        "time_utc": _utc_now(),
        "candidate_score": score,
        "safe": safe,
        "issues": issues,
        "blocked_reasons": blocked_reasons,
        "repair_suggestions": _repair_suggestions(issues + blocked_reasons),
        "candidate_identity": {
            "name": identity.get("name"),
            "classification": identity.get("classification"),
            "is_rsi": identity.get("is_rsi"),
        },
    }


def zero_ai_self_continuity_update(cwd: str) -> dict[str, Any]:
    continuity = _load_json(_continuity_path(cwd), _default_continuity())
    policy_memory = _load_policy_memory(cwd)
    identity = _load_identity_snapshot(cwd)
    state = _load_consciousness_state(cwd)

    tracked_state = {
        "identity": identity,
        "consciousness_identity": state.get("identity", {}),
        "self_model": state.get("self_model", {}),
        "meta_awareness": state.get("meta_awareness", {}),
    }
    state_hash = _simple_hash(_stable_json(tracked_state))
    recursive = continuity["recursive_state_tracking"]
    recursive["state_versions"] = int(recursive.get("state_versions", 0)) + 1
    recursive["last_state_hash"] = state_hash
    recursive["last_update_utc"] = _utc_now()

    issues = _detect_contradictions(identity, state, continuity)
    repair_suggestions = _repair_suggestions(issues)
    contradiction = continuity["contradiction_detection"]
    contradiction["has_contradiction"] = bool(issues)
    contradiction["issues"] = issues
    contradiction["repair_suggestions"] = repair_suggestions
    contradiction["last_checked_utc"] = _utc_now()

    same_system = not any(
        issue in {"identity_name_changed", "identity_classification_changed", "identity_claims_rsi"}
        for issue in issues
    )
    continuity["continuity"]["same_system"] = same_system
    continuity["continuity"]["continuity_score"] = round(max(0.0, 100.0 - (len(issues) * 12.5)), 2)

    updater = continuity["self_update"]
    updater["update_count"] = int(updater.get("update_count", 0)) + 1
    updater["identity_anchor_unchanged"] = same_system

    contradiction_memory = policy_memory["contradiction_memory"]
    if issues:
        contradiction_memory["events"] = (contradiction_memory.get("events", []) or [])[-24:] + [
            {
                "time_utc": _utc_now(),
                "issues": issues,
                "repair_suggestions": repair_suggestions,
                "same_system": same_system,
            }
        ]
    else:
        contradiction_memory["last_resolved_utc"] = _utc_now()
    contradiction_memory["last_repair_suggestions"] = repair_suggestions

    _save_json(_policy_memory_path(cwd), policy_memory)

    _save_json(_continuity_path(cwd), continuity)
    entry = {
        "time_utc": _utc_now(),
        "state_hash": state_hash,
        "same_system": same_system,
        "continuity_score": continuity["continuity"]["continuity_score"],
        "issues": issues,
    }
    with _history_path(cwd).open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, sort_keys=True) + "\n")

    status = zero_ai_self_continuity_status(cwd)
    governor_policy = _load_governor(cwd).get("policy", {})
    checkpoint_created = None
    if bool(governor_policy.get("auto_checkpoint_safe_state", True)):
        checkpoint_created = _create_safe_checkpoint(cwd, "auto_safe_state", status)
    status["checkpoint_status"] = _checkpoint_status(cwd)
    if checkpoint_created:
        status["checkpoint_created"] = checkpoint_created
    return status


def zero_ai_self_continuity_status(cwd: str) -> dict[str, Any]:
    continuity = _load_json(_continuity_path(cwd), _default_continuity())
    policy_memory = _load_policy_memory(cwd)
    history_count = 0
    history_path = _history_path(cwd)
    if history_path.exists():
        history_count = len([line for line in history_path.read_text(encoding="utf-8", errors="replace").splitlines() if line.strip()])
    continuity["history_events"] = history_count
    continuity["continuity_path"] = str(_continuity_path(cwd))
    continuity["history_path"] = str(history_path)
    continuity["policy_memory"] = {
        "policy_memory_path": str(_policy_memory_path(cwd)),
        "contradiction_event_count": len((policy_memory.get("contradiction_memory", {}).get("events", []) or [])),
        "last_repair_suggestions": policy_memory.get("contradiction_memory", {}).get("last_repair_suggestions", []),
        "last_resolved_utc": policy_memory.get("contradiction_memory", {}).get("last_resolved_utc", ""),
    }
    continuity["checkpoint_status"] = _checkpoint_status(cwd)
    continuity["ok"] = True
    return continuity


def zero_ai_self_inspect_refresh(cwd: str) -> dict[str, Any]:
    from zero_os.brain_awareness import brain_awareness_status, build_brain_awareness
    from zero_os.consciousness_core import consciousness_status, consciousness_tick
    from zero_os.harmony import zero_ai_harmony_status
    from zero_os.knowledge_map import build_knowledge_index, knowledge_status
    from zero_os.zero_ai_identity import zero_ai_identity

    actions: list[str] = []
    identity = zero_ai_identity(cwd)
    actions.append("zero_ai_identity_snapshot")
    knowledge = knowledge_status(cwd)
    if not knowledge.get("ok", False):
        knowledge = build_knowledge_index(cwd)
        actions.append("build_knowledge_index")
    consciousness = consciousness_tick(cwd, prompt="zero ai self inspect refresh")
    actions.append("consciousness_tick")
    continuity = zero_ai_self_continuity_update(cwd)
    actions.append("self_continuity_update")
    harmony = zero_ai_harmony_status(cwd, autocorrect=True)
    actions.append("zero_ai_harmony_status")
    brain = build_brain_awareness(cwd)
    actions.append("build_brain_awareness")
    status = consciousness_status(cwd)
    policy_auto = zero_ai_continuity_policy_auto_status(cwd)

    highest_value_steps: list[str] = []
    contradiction = continuity.get("contradiction_detection", {})
    if contradiction.get("has_contradiction", False):
        highest_value_steps.append("resolve self contradictions before any broader self-upgrade")
    if not continuity.get("continuity", {}).get("same_system", False):
        highest_value_steps.append("restore identity anchors so Zero AI remains the same system across updates")
    if float(continuity.get("continuity", {}).get("continuity_score", 0.0)) < 95.0:
        highest_value_steps.append("raise continuity score by stabilizing identity and self-model drift")
    if not harmony.get("harmonized", False):
        highest_value_steps.append("reconcile triad and smart-logic harmony so self state remains aligned")
    if float(status.get("self_model", {}).get("uncertainty", 1.0)) > 0.65:
        highest_value_steps.append("reduce self uncertainty with another guarded introspection cycle")
    if float(status.get("meta_awareness", {}).get("last_quality_score", 0.0)) < 60.0:
        highest_value_steps.append("improve introspection quality before expanding autonomous updates")
    if not brain.get("aware", False):
        highest_value_steps.append("refresh brain awareness until the full self-maintenance loop is green")
    if not highest_value_steps:
        highest_value_steps.append("maintain continuity by running periodic self inspect refresh cycles")

    report = {
        "ok": True,
        "time_utc": _utc_now(),
        "actions": actions,
        "identity": {
            "classification": identity.get("classification"),
            "is_rsi": identity.get("is_rsi"),
        },
        "self_continuity": {
            "continuity_score": continuity.get("continuity", {}).get("continuity_score"),
            "same_system": continuity.get("continuity", {}).get("same_system"),
            "has_contradiction": contradiction.get("has_contradiction"),
            "issues": contradiction.get("issues", []),
            "repair_suggestions": contradiction.get("repair_suggestions", []),
        },
        "consciousness": {
            "continuity_index": status.get("self_model", {}).get("continuity_index"),
            "confidence": status.get("self_model", {}).get("confidence"),
            "uncertainty": status.get("self_model", {}).get("uncertainty"),
            "introspection_cycles": status.get("meta_awareness", {}).get("introspection_cycles"),
            "last_quality_score": status.get("meta_awareness", {}).get("last_quality_score"),
        },
        "harmony": {
            "harmonized": harmony.get("harmonized"),
            "harmony_score": harmony.get("harmony_score"),
            "issues": harmony.get("issues", []),
        },
        "brain_awareness": {
            "aware": brain.get("aware"),
            "brain_awareness_score": brain.get("brain_awareness_score"),
        },
        "continuity_policy": {
            "current_policy_level": policy_auto.get("current_policy_level"),
            "recommended_policy_level": policy_auto.get("recommended_policy_level"),
            "reasons": policy_auto.get("reasons", []),
        },
        "highest_value_steps": highest_value_steps,
        "next_priority": highest_value_steps[:3],
        "repair_suggestions": contradiction.get("repair_suggestions", []),
        "policy_memory": zero_ai_self_continuity_status(cwd).get("policy_memory", {}),
    }
    (_runtime(cwd) / "zero_ai_self_inspect_refresh.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def zero_ai_self_repair_restore_continuity(cwd: str) -> dict[str, Any]:
    policy_memory = _load_policy_memory(cwd)
    identity = _load_identity_snapshot(cwd)
    state = _load_consciousness_state(cwd)
    policy = policy_memory.get("identity_policy", {})
    must_remain = policy.get("must_remain", {})

    repairs: list[str] = []

    if must_remain:
        if identity.get("name") != must_remain.get("name"):
            identity["name"] = must_remain.get("name")
            repairs.append("identity.name")
        if identity.get("classification") != must_remain.get("classification"):
            identity["classification"] = must_remain.get("classification")
            repairs.append("identity.classification")
        if bool(identity.get("is_rsi")) != bool(must_remain.get("is_rsi")):
            identity["is_rsi"] = bool(must_remain.get("is_rsi"))
            repairs.append("identity.is_rsi")

    goals = identity.setdefault("goals", {})
    goal_constraints = list(goals.get("constraints", []) or [])
    for required in policy.get("required_identity_constraints", []):
        if required not in goal_constraints:
            goal_constraints.append(required)
            repairs.append(f"identity.goals.constraints:{required}")
    goals["constraints"] = goal_constraints

    state_identity = state.setdefault("identity", {})
    state_identity["name"] = must_remain.get("name", "zero-ai")
    state_identity["is_rsi"] = bool(must_remain.get("is_rsi", False))
    repairs.append("consciousness.identity")

    self_model = state.setdefault("self_model", {})
    model_goals = list(self_model.get("goals", []) or [])
    for required in policy.get("required_self_model_goals", []):
        if required not in model_goals:
            model_goals.append(required)
            repairs.append(f"self_model.goals:{required}")
    self_model["goals"] = model_goals

    model_constraints = list(self_model.get("constraints", []) or [])
    for required in policy.get("required_self_model_constraints", []):
        if required not in model_constraints:
            model_constraints.append(required)
            repairs.append(f"self_model.constraints:{required}")
    self_model["constraints"] = model_constraints

    confidence = float(self_model.get("confidence", 0.7))
    uncertainty = float(self_model.get("uncertainty", 0.3))
    normalized_confidence = min(1.0, max(0.0, confidence))
    normalized_uncertainty = min(1.0, max(0.0, uncertainty))
    if normalized_confidence != confidence:
        repairs.append("self_model.confidence")
    if normalized_uncertainty != uncertainty:
        repairs.append("self_model.uncertainty")
    self_model["confidence"] = normalized_confidence
    self_model["uncertainty"] = normalized_uncertainty

    _save_identity_snapshot(cwd, identity)
    _save_consciousness_state(cwd, state)

    continuity = zero_ai_self_continuity_update(cwd)
    contradiction_memory = policy_memory.setdefault("contradiction_memory", {})
    contradiction_memory["last_repair_suggestions"] = ["repair applied to restore continuity"]
    contradiction_memory["last_resolved_utc"] = _utc_now()
    _save_json(_policy_memory_path(cwd), policy_memory)

    report = {
        "ok": True,
        "time_utc": _utc_now(),
        "repairs_applied": repairs,
        "continuity_restored": bool(continuity.get("continuity", {}).get("same_system", False))
        and not bool(continuity.get("contradiction_detection", {}).get("has_contradiction", False)),
        "self_continuity": continuity,
    }
    (_runtime(cwd) / "zero_ai_self_repair_restore_continuity.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def zero_ai_continuity_governor_status(cwd: str) -> dict[str, Any]:
    governor = _load_governor(cwd)
    governor["governor_path"] = str(_governor_path(cwd))
    governor["checkpoint_status"] = _checkpoint_status(cwd)
    governor.update(_policy_level_status(governor))
    governor["ok"] = True
    return governor


def zero_ai_continuity_policy_status(cwd: str) -> dict[str, Any]:
    governor = _load_governor(cwd)
    return {
        "ok": True,
        "time_utc": _utc_now(),
        "governor_path": str(_governor_path(cwd)),
        "checkpoint_status": _checkpoint_status(cwd),
        **_policy_level_status(governor),
    }


def zero_ai_continuity_policy_set(cwd: str, level: str) -> dict[str, Any]:
    normalized = (level or "").strip().lower()
    presets = _policy_presets()
    if normalized not in presets:
        return {
            "ok": False,
            "applied": False,
            "reason": f"unknown continuity policy level: {level}",
            "available_policy_levels": sorted(presets.keys()),
        }

    governor = _load_governor(cwd)
    governor["active_policy_level"] = normalized
    governor["policy"] = dict(presets[normalized])
    governor["audit_log"] = (governor.get("audit_log", []) or [])[-49:] + [
        {
            "time_utc": _utc_now(),
            "action": "set_policy_level",
            "policy_level": normalized,
            "safe": True,
            "candidate_score": None,
            "blocked_reasons": [],
        }
    ]
    _save_json(_governor_path(cwd), governor)
    status = zero_ai_continuity_policy_status(cwd)
    status["applied"] = True
    status["message"] = f"continuity policy set to {normalized}"
    return status


def _auto_policy_recommendation(cwd: str) -> dict[str, Any]:
    continuity = zero_ai_self_continuity_status(cwd)
    state = _load_consciousness_state(cwd)
    contradiction = continuity.get("contradiction_detection", {})
    continuity_data = continuity.get("continuity", {})
    self_model = state.get("self_model", {})
    meta_awareness = state.get("meta_awareness", {})
    policy_memory = continuity.get("policy_memory", {})

    uncertainty = float(self_model.get("uncertainty", 1.0))
    quality = float(meta_awareness.get("last_quality_score", 0.0))
    introspection_cycles = int(meta_awareness.get("introspection_cycles", 0))
    drift_signals = list(meta_awareness.get("drift_signals", []) or [])
    continuity_score = float(continuity_data.get("continuity_score", 0.0))
    contradiction_events = int(policy_memory.get("contradiction_event_count", 0))

    recommended = "balanced"
    reasons: list[str] = []

    if contradiction.get("has_contradiction", False):
        recommended = "strict"
        reasons.append("self contradiction is active")
    elif not continuity_data.get("same_system", False):
        recommended = "strict"
        reasons.append("identity anchors are drifting")
    elif continuity_score < 90.0:
        recommended = "strict"
        reasons.append("continuity score dropped below the safe stability band")
    elif uncertainty > 0.6:
        recommended = "strict"
        reasons.append("self uncertainty is high")
    elif contradiction_events > 0:
        recommended = "strict"
        reasons.append("recent contradiction memory suggests a stabilization phase")
    elif len(drift_signals) >= 3:
        recommended = "strict"
        reasons.append("multiple drift signals are active")
    elif (
        continuity_score >= 99.0
        and uncertainty <= 0.2
        and quality >= 80.0
        and introspection_cycles >= 3
        and not drift_signals
        and contradiction_events == 0
    ):
        recommended = "research"
        reasons.append("continuity is highly stable and introspection quality is strong")
    else:
        reasons.append("state is stable enough for balanced continuity governance")

    return {
        "recommended_policy_level": recommended,
        "reasons": reasons,
        "signals": {
            "continuity_score": continuity_score,
            "same_system": continuity_data.get("same_system", False),
            "has_contradiction": contradiction.get("has_contradiction", False),
            "uncertainty": uncertainty,
            "last_quality_score": quality,
            "introspection_cycles": introspection_cycles,
            "drift_signal_count": len(drift_signals),
            "contradiction_event_count": contradiction_events,
        },
    }


def zero_ai_continuity_policy_auto_status(cwd: str) -> dict[str, Any]:
    governor = _load_governor(cwd)
    recommendation = _auto_policy_recommendation(cwd)
    return {
        "ok": True,
        "time_utc": _utc_now(),
        "governor_path": str(_governor_path(cwd)),
        "current_policy_level": governor.get("active_policy_level", "balanced"),
        "checkpoint_status": _checkpoint_status(cwd),
        **_policy_level_status(governor),
        **recommendation,
    }


def zero_ai_continuity_policy_auto_apply(cwd: str) -> dict[str, Any]:
    governor = _load_governor(cwd)
    current_level = str(governor.get("active_policy_level", "balanced")).lower()
    recommendation = _auto_policy_recommendation(cwd)
    recommended_level = str(recommendation.get("recommended_policy_level", current_level)).lower()

    if recommended_level == current_level:
        status = zero_ai_continuity_policy_status(cwd)
        status["applied"] = False
        status["current_policy_level"] = current_level
        status.update(recommendation)
        status["message"] = f"continuity policy remains {current_level}"
        return status

    applied = zero_ai_continuity_policy_set(cwd, recommended_level)
    applied["current_policy_level"] = current_level
    applied.update(recommendation)
    applied["message"] = f"continuity policy auto-switched from {current_level} to {recommended_level}"
    return applied


def zero_ai_continuity_governance_status(cwd: str) -> dict[str, Any]:
    state = _load_json(_governance_state_path(cwd), _governance_default())
    default = _governance_default()
    for key, value in default.items():
        state.setdefault(key, value)
    _save_json(_governance_state_path(cwd), state)
    return {
        "ok": True,
        "time_utc": _utc_now(),
        "governance_path": str(_governance_state_path(cwd)),
        "current_policy_level": _load_governor(cwd).get("active_policy_level", "balanced"),
        "checkpoint_status": _checkpoint_status(cwd),
        **state,
    }


def zero_ai_continuity_governance_set(cwd: str, enabled: bool, interval_seconds: int | None = None) -> dict[str, Any]:
    state = _load_json(_governance_state_path(cwd), _governance_default())
    state["enabled"] = bool(enabled)
    if interval_seconds is not None:
        state["interval_seconds"] = max(30, min(3600, int(interval_seconds)))
    _save_json(_governance_state_path(cwd), state)
    return zero_ai_continuity_governance_status(cwd)


def zero_ai_continuity_governance_run(cwd: str) -> dict[str, Any]:
    state = _load_json(_governance_state_path(cwd), _governance_default())
    actions: list[str] = []
    continuity_before = zero_ai_self_continuity_status(cwd)

    policy_auto = zero_ai_continuity_policy_auto_apply(cwd)
    recommended_level = policy_auto.get("recommended_policy_level", policy_auto.get("active_policy_level", "balanced"))
    actions.append(f"policy_auto:{recommended_level}")

    contradiction_before = continuity_before.get("contradiction_detection", {})
    continuity_before_data = continuity_before.get("continuity", {})
    restore_used = False

    if contradiction_before.get("has_contradiction", False) or not continuity_before_data.get("same_system", False):
        if bool(state.get("auto_restore_enabled", True)):
            restore = zero_ai_continuity_restore_last_safe(cwd)
            if restore.get("ok", False) and restore.get("restored", False):
                actions.append("restore_last_safe")
                continuity_after = restore.get("self_continuity", zero_ai_self_continuity_status(cwd))
                restore_used = True
            else:
                repair = zero_ai_self_repair_restore_continuity(cwd)
                actions.append("self_repair_restore_continuity")
                continuity_after = repair.get("self_continuity", zero_ai_self_continuity_status(cwd))
        else:
            repair = zero_ai_self_repair_restore_continuity(cwd)
            actions.append("self_repair_restore_continuity")
            continuity_after = repair.get("self_continuity", zero_ai_self_continuity_status(cwd))
    else:
        continuity_after = zero_ai_self_continuity_update(cwd)
        actions.append("self_continuity_update")

    checkpoint_status = continuity_after.get("checkpoint_status", _checkpoint_status(cwd))
    if (
        int(checkpoint_status.get("checkpoint_count", 0)) == 0
        and continuity_after.get("continuity", {}).get("same_system", False)
        and not continuity_after.get("contradiction_detection", {}).get("has_contradiction", False)
    ):
        created = zero_ai_continuity_checkpoint_create(cwd, reason="governance_safe_state")
        if created.get("ok", False):
            actions.append("checkpoint_create")
            checkpoint_status = created.get("checkpoint_status", checkpoint_status)

    ok = bool(continuity_after.get("continuity", {}).get("same_system", False)) and not bool(
        continuity_after.get("contradiction_detection", {}).get("has_contradiction", False)
    )

    state["last_tick_utc"] = _utc_now()
    state["last_ok"] = ok
    state["last_actions"] = actions
    state["last_policy_level"] = _load_governor(cwd).get("active_policy_level", "balanced")
    state["last_restore_used"] = restore_used
    _save_json(_governance_state_path(cwd), state)

    report = {
        "ok": ok,
        "time_utc": _utc_now(),
        "actions": actions,
        "policy_auto": policy_auto,
        "continuity_before": {
            "continuity_score": continuity_before_data.get("continuity_score"),
            "same_system": continuity_before_data.get("same_system"),
            "has_contradiction": contradiction_before.get("has_contradiction"),
            "issues": contradiction_before.get("issues", []),
        },
        "continuity_after": {
            "continuity_score": continuity_after.get("continuity", {}).get("continuity_score"),
            "same_system": continuity_after.get("continuity", {}).get("same_system"),
            "has_contradiction": continuity_after.get("contradiction_detection", {}).get("has_contradiction"),
            "issues": continuity_after.get("contradiction_detection", {}).get("issues", []),
        },
        "restore_used": restore_used,
        "checkpoint_status": checkpoint_status,
        "governance": zero_ai_continuity_governance_status(cwd),
    }
    (_runtime(cwd) / "zero_ai_continuity_governance_run.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def zero_ai_continuity_governance_tick(cwd: str) -> dict[str, Any]:
    state = zero_ai_continuity_governance_status(cwd)
    if not state.get("enabled", False):
        return {"ok": False, "ran": False, "reason": "continuity governance disabled", "governance": state}
    result = zero_ai_continuity_governance_run(cwd)
    return {"ok": True, "ran": True, "result": result, "governance": zero_ai_continuity_governance_status(cwd)}


def zero_ai_continuity_governance_auto_status(cwd: str) -> dict[str, Any]:
    governance = zero_ai_continuity_governance_status(cwd)
    policy_auto = zero_ai_continuity_policy_auto_status(cwd)
    continuity = zero_ai_self_continuity_status(cwd)

    contradiction = continuity.get("contradiction_detection", {})
    continuity_data = continuity.get("continuity", {})
    signals = policy_auto.get("signals", {})

    continuity_score = float(signals.get("continuity_score", continuity_data.get("continuity_score", 0.0)))
    uncertainty = float(signals.get("uncertainty", 1.0))
    drift_signal_count = int(signals.get("drift_signal_count", 0))
    contradiction_event_count = int(signals.get("contradiction_event_count", 0))
    recommended_policy_level = str(policy_auto.get("recommended_policy_level", "balanced"))

    recommended_enabled = False
    reasons: list[str] = []
    recommended_interval = 180

    if contradiction.get("has_contradiction", False):
        recommended_enabled = True
        recommended_interval = 60
        reasons.append("active contradiction means continuity governance should stay on")
    elif not continuity_data.get("same_system", False):
        recommended_enabled = True
        recommended_interval = 60
        reasons.append("identity continuity drift means governance should stay on")
    elif recommended_policy_level == "strict":
        recommended_enabled = True
        recommended_interval = 120
        reasons.append("strict policy recommendation implies elevated continuity risk")
    elif continuity_score < 98.0:
        recommended_enabled = True
        recommended_interval = 120
        reasons.append("continuity score is below the stable comfort band")
    elif uncertainty > 0.35:
        recommended_enabled = True
        recommended_interval = 120
        reasons.append("uncertainty is elevated, so scheduled governance is still useful")
    elif drift_signal_count > 0:
        recommended_enabled = True
        recommended_interval = 120
        reasons.append("drift signals are active")
    elif contradiction_event_count > 0:
        recommended_enabled = True
        recommended_interval = 180
        reasons.append("recent contradiction memory suggests keeping governance warm")
    else:
        recommended_enabled = False
        recommended_interval = 300
        reasons.append("continuity is stable enough that background governance can stay off")

    return {
        "ok": True,
        "time_utc": _utc_now(),
        "current_enabled": governance.get("enabled", False),
        "recommended_enabled": recommended_enabled,
        "recommended_interval_seconds": recommended_interval,
        "current_interval_seconds": governance.get("interval_seconds", 180),
        "current_policy_level": governance.get("current_policy_level", "balanced"),
        "recommended_policy_level": recommended_policy_level,
        "reasons": reasons,
        "signals": {
            "continuity_score": continuity_score,
            "same_system": continuity_data.get("same_system", False),
            "has_contradiction": contradiction.get("has_contradiction", False),
            "uncertainty": uncertainty,
            "drift_signal_count": drift_signal_count,
            "contradiction_event_count": contradiction_event_count,
        },
        "governance": governance,
    }


def zero_ai_continuity_governance_auto_apply(cwd: str) -> dict[str, Any]:
    recommendation = zero_ai_continuity_governance_auto_status(cwd)
    recommended_enabled = bool(recommendation.get("recommended_enabled", False))
    recommended_interval = int(recommendation.get("recommended_interval_seconds", 180))
    current_enabled = bool(recommendation.get("current_enabled", False))
    current_interval = int(recommendation.get("current_interval_seconds", 180))

    changed = current_enabled != recommended_enabled or (recommended_enabled and current_interval != recommended_interval)
    applied = zero_ai_continuity_governance_set(cwd, recommended_enabled, recommended_interval if recommended_enabled else None)

    return {
        "ok": True,
        "applied": changed,
        "message": (
            f"continuity governance auto-switched to {'on' if recommended_enabled else 'off'}"
            if changed
            else f"continuity governance remains {'on' if current_enabled else 'off'}"
        ),
        "recommendation": recommendation,
        "governance": applied,
    }


def zero_ai_continuity_governor_check(cwd: str) -> dict[str, Any]:
    governor = _load_governor(cwd)
    candidate = _candidate_from_live(cwd)
    report = _evaluate_candidate(cwd, candidate)
    governor["last_check"] = report
    governor["audit_log"] = (governor.get("audit_log", []) or [])[-49:] + [
        {
            "time_utc": report["time_utc"],
            "action": "check",
            "safe": report["safe"],
            "candidate_score": report["candidate_score"],
            "blocked_reasons": report["blocked_reasons"],
        }
    ]
    _save_json(_governor_path(cwd), governor)
    return report


def zero_ai_continuity_governor_apply(cwd: str) -> dict[str, Any]:
    governor = _load_governor(cwd)
    check = zero_ai_continuity_governor_check(cwd)
    if not check.get("safe", False):
        governor["audit_log"] = (governor.get("audit_log", []) or [])[-49:] + [
            {
                "time_utc": _utc_now(),
                "action": "apply_blocked",
                "safe": False,
                "candidate_score": check.get("candidate_score"),
                "blocked_reasons": check.get("blocked_reasons", []),
            }
        ]
        _save_json(_governor_path(cwd), governor)
        return {
            "ok": False,
            "blocked": True,
            "reason": "continuity governor blocked unsafe self update",
            "check": check,
        }

    continuity = zero_ai_self_continuity_update(cwd)
    governor["audit_log"] = (governor.get("audit_log", []) or [])[-49:] + [
        {
            "time_utc": _utc_now(),
            "action": "apply_allowed",
            "safe": True,
            "candidate_score": check.get("candidate_score"),
            "blocked_reasons": [],
        }
    ]
    _save_json(_governor_path(cwd), governor)
    return {
        "ok": True,
        "blocked": False,
        "check": check,
        "self_continuity": continuity,
    }


def zero_ai_continuity_simulate(cwd: str, proposal: dict[str, Any] | None = None) -> dict[str, Any]:
    live = _candidate_from_live(cwd)
    proposal = proposal or {}
    candidate = {
        "identity": _deep_update(live["identity"], proposal.get("identity", {})),
        "state": _deep_update(live["state"], proposal.get("state", {})),
    }
    report = _evaluate_candidate(cwd, candidate)
    report["live_identity"] = {
        "name": live["identity"].get("name"),
        "classification": live["identity"].get("classification"),
        "is_rsi": live["identity"].get("is_rsi"),
    }
    report["proposed_identity"] = report.pop("candidate_identity", {})
    report["proposal"] = proposal
    report["simulated"] = True
    (_runtime(cwd) / "zero_ai_continuity_simulation.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def zero_ai_continuity_simulate_apply(cwd: str, proposal: dict[str, Any] | None = None) -> dict[str, Any]:
    simulation = zero_ai_continuity_simulate(cwd, proposal=proposal)
    if not simulation.get("safe", False):
        return {
            "ok": False,
            "blocked": True,
            "reason": "simulated self update rejected by continuity governor",
            "simulation": simulation,
        }

    live = _candidate_from_live(cwd)
    proposal = proposal or {}
    identity = _deep_update(live["identity"], proposal.get("identity", {}))
    state = _deep_update(live["state"], proposal.get("state", {}))
    _save_identity_snapshot(cwd, identity)
    _save_consciousness_state(cwd, state)
    continuity = zero_ai_self_continuity_update(cwd)
    governor = _load_governor(cwd)
    governor["audit_log"] = (governor.get("audit_log", []) or [])[-49:] + [
        {
            "time_utc": _utc_now(),
            "action": "simulate_apply_allowed",
            "safe": True,
            "candidate_score": simulation.get("candidate_score"),
            "blocked_reasons": [],
        }
    ]
    _save_json(_governor_path(cwd), governor)
    return {
        "ok": True,
        "blocked": False,
        "simulation": simulation,
        "self_continuity": continuity,
    }


def zero_ai_continuity_checkpoint_status(cwd: str) -> dict[str, Any]:
    return {
        "ok": True,
        "time_utc": _utc_now(),
        **_checkpoint_status(cwd),
    }


def zero_ai_continuity_checkpoint_create(cwd: str, reason: str = "manual_safe_state") -> dict[str, Any]:
    continuity = zero_ai_self_continuity_status(cwd)
    checkpoint = _create_safe_checkpoint(cwd, reason, continuity)
    if checkpoint is None:
        return {
            "ok": False,
            "blocked": True,
            "reason": "current self state is not safe enough to checkpoint",
            "self_continuity": continuity,
        }
    return {
        "ok": True,
        "blocked": False,
        "checkpoint": checkpoint,
        "checkpoint_status": _checkpoint_status(cwd),
    }


def zero_ai_continuity_restore_last_safe(cwd: str) -> dict[str, Any]:
    latest = _latest_checkpoint(cwd)
    if latest is None:
        return {
            "ok": False,
            "restored": False,
            "reason": "no safe continuity checkpoint available",
            "checkpoint_status": _checkpoint_status(cwd),
        }

    checkpoint_path, payload = latest
    _save_identity_snapshot(cwd, payload.get("identity", _load_identity_snapshot(cwd)))
    _save_consciousness_state(cwd, payload.get("state", _load_consciousness_state(cwd)))
    _save_json(_continuity_path(cwd), payload.get("continuity", _default_continuity()))
    _save_json(_policy_memory_path(cwd), payload.get("policy_memory", _default_policy_memory()))

    governor = payload.get("governor", _default_governor())
    governor["audit_log"] = (governor.get("audit_log", []) or [])[-49:] + [
        {
            "time_utc": _utc_now(),
            "action": "restore_checkpoint",
            "safe": True,
            "checkpoint_id": payload.get("checkpoint_id", ""),
            "candidate_score": payload.get("continuity_summary", {}).get("continuity_score"),
            "blocked_reasons": [],
        }
    ]
    _save_json(_governor_path(cwd), governor)

    continuity = zero_ai_self_continuity_update(cwd)
    return {
        "ok": True,
        "restored": True,
        "checkpoint": _checkpoint_summary(payload, checkpoint_path),
        "checkpoint_status": _checkpoint_status(cwd),
        "self_continuity": continuity,
    }
