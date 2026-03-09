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
    return {
        "schema_version": 1,
        "policy": {
            "min_safe_score": 85.0,
            "block_identity_anchor_changes": True,
            "block_rsi_flip": True,
            "block_missing_core_constraints": True,
        },
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
    return _load_json(_governor_path(cwd), _default_governor())


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
    return zero_ai_self_continuity_status(cwd)


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
    governor["ok"] = True
    return governor


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
