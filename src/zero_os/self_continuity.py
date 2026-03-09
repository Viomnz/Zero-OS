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


def zero_ai_self_continuity_update(cwd: str) -> dict[str, Any]:
    continuity = _load_json(_continuity_path(cwd), _default_continuity())
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
    contradiction = continuity["contradiction_detection"]
    contradiction["has_contradiction"] = bool(issues)
    contradiction["issues"] = issues
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
    history_count = 0
    history_path = _history_path(cwd)
    if history_path.exists():
        history_count = len([line for line in history_path.read_text(encoding="utf-8", errors="replace").splitlines() if line.strip()])
    continuity["history_events"] = history_count
    continuity["continuity_path"] = str(_continuity_path(cwd))
    continuity["history_path"] = str(history_path)
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
    }
    (_runtime(cwd) / "zero_ai_self_inspect_refresh.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report
