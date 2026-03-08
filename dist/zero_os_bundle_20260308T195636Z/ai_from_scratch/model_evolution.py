from __future__ import annotations

import json
from pathlib import Path


def _path(cwd: str) -> Path:
    p = Path(cwd).resolve() / ".zero_os" / "runtime" / "model_evolution.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _load(cwd: str) -> dict:
    p = _path(cwd)
    if not p.exists():
        return {"version": 1, "history": [], "last_action": None}
    try:
        raw = json.loads(p.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {"version": 1, "history": [], "last_action": None}
    return {
        "version": int(raw.get("version", 1)),
        "history": list(raw.get("history", []))[-200:],
        "last_action": raw.get("last_action"),
    }


def _save(cwd: str, data: dict) -> None:
    _path(cwd).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def evaluate_evolution_need(rejection_rate: float, prediction_error: float, signal_instability: float) -> dict:
    trigger = rejection_rate >= 0.6 or prediction_error >= 0.5 or signal_instability >= 0.45
    method = None
    if trigger:
        if prediction_error >= 0.5:
            method = "parameter_tuning"
        elif signal_instability >= 0.45:
            method = "rule_modification"
        else:
            method = "model_replacement"
    return {
        "trigger": trigger,
        "method": method,
        "metrics": {
            "rejection_rate": round(float(rejection_rate), 4),
            "prediction_error": round(float(prediction_error), 4),
            "signal_instability": round(float(signal_instability), 4),
        },
    }


def apply_evolution(cwd: str, decision: dict, reasoner_state: dict) -> dict:
    data = _load(cwd)
    changed = False
    action = {"triggered": False, "method": None, "changes": {}}
    if decision.get("trigger"):
        action["triggered"] = True
        action["method"] = decision.get("method")
        method = str(decision.get("method"))
        if method == "parameter_tuning":
            reasoner_state["profile"] = "adaptive"
            action["changes"]["profile"] = "adaptive"
            changed = True
        elif method == "rule_modification":
            reasoner_state["mode"] = "exploration"
            action["changes"]["mode"] = "exploration"
            changed = True
        elif method == "model_replacement":
            reasoner_state["model_generation"] = int(reasoner_state.get("model_generation", 1)) + 1
            action["changes"]["model_generation"] = reasoner_state["model_generation"]
            changed = True

    data["history"].append(
        {
            "decision": decision,
            "action": action,
        }
    )
    data["history"] = data["history"][-200:]
    data["last_action"] = action
    if changed:
        data["version"] = int(data.get("version", 1)) + 1
    _save(cwd, data)
    return {"evolution_version": data["version"], "action": action, "decision": decision}
