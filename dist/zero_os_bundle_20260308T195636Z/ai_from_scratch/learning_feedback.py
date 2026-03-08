from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _runtime(cwd: str) -> Path:
    p = Path(cwd).resolve() / ".zero_os" / "runtime"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _load(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return default


def _save(path: Path, payload) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def apply_learning_feedback(
    cwd: str,
    prompt: str,
    predicted: dict,
    observed: dict,
    context: dict,
) -> dict:
    path = _runtime(cwd) / "learning_feedback.json"
    data = _load(
        path,
        {"history": [], "stats": {"success": 0, "failure": 0, "drift": 0, "positive": 0, "negative": 0, "neutral": 0}},
    )

    predicted_pass = bool(predicted.get("expected_success", False))
    observed_pass = bool(observed.get("actual_success", False))
    outcome_match = predicted_pass == observed_pass

    prediction_score = float(predicted.get("prediction_score", 0.0))
    efficiency = float(observed.get("efficiency_score", 0.0))
    reliability = float(observed.get("signal_reliability", 0.0))
    goal_alignment = float(observed.get("goal_alignment_score", 1.0 if observed_pass else 0.0))
    stability_impact = float(observed.get("stability_impact", 1.0 if observed_pass else 0.0))
    learning_score = round(
        (prediction_score * 0.25)
        + (efficiency * 0.25)
        + (reliability * 0.2)
        + (goal_alignment * 0.15)
        + (stability_impact * 0.15),
        4,
    )

    signal_type = "neutral"
    if observed_pass and learning_score >= 0.72 and stability_impact >= 0.6:
        signal_type = "positive"
    elif (not observed_pass) or learning_score < 0.45 or stability_impact < 0.4:
        signal_type = "negative"

    actions = {
        "adjust_reasoning_parameters": False,
        "update_environment_model": False,
        "refine_survival_evaluator": False,
    }
    if not outcome_match or learning_score < 0.55:
        actions["adjust_reasoning_parameters"] = True
    if efficiency < 0.5:
        actions["update_environment_model"] = True
    if reliability < 0.6:
        actions["refine_survival_evaluator"] = True

    learning_signals = {
        "strategy_adjustment": bool(actions["adjust_reasoning_parameters"]),
        "model_correction": bool(actions["update_environment_model"]),
        "memory_update": signal_type != "neutral",
    }

    stats = data.get("stats", {"success": 0, "failure": 0, "drift": 0, "positive": 0, "negative": 0, "neutral": 0})
    if observed_pass:
        stats["success"] = int(stats.get("success", 0)) + 1
    else:
        stats["failure"] = int(stats.get("failure", 0)) + 1
    if not outcome_match:
        stats["drift"] = int(stats.get("drift", 0)) + 1
    stats[signal_type] = int(stats.get(signal_type, 0)) + 1

    entry = {
        "time_utc": _utc_now(),
        "prompt": prompt,
        "predicted": predicted,
        "observed": observed,
        "context_mode": str(context.get("reasoning_parameters", {}).get("priority_mode", "normal")),
        "outcome_match": outcome_match,
        "learning_score": learning_score,
        "signal_type": signal_type,
        "actions": actions,
        "learning_signals": learning_signals,
    }
    history = list(data.get("history", []))
    history.append(entry)
    data["history"] = history[-500:]
    data["stats"] = stats
    data["last"] = entry
    _save(path, data)

    return {
        "ok": True,
        "outcome_match": outcome_match,
        "learning_score": learning_score,
        "signal_type": signal_type,
        "actions": actions,
        "learning_signals": learning_signals,
        "stats": stats,
        "history_size": len(data["history"]),
    }
