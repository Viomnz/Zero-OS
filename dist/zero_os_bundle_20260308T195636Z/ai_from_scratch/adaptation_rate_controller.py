from __future__ import annotations

import json
from pathlib import Path


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


def control_adaptation_rate(cwd: str, feedback: dict, context: dict, novelty: dict | None = None) -> dict:
    rt = _runtime(cwd)
    path = rt / "adaptation_rate.json"
    state = _load(path, {"history": [], "mode": "moderate", "rate": 0.5})

    learning_score = float(feedback.get("learning_score", 0.5))
    mismatch = not bool(feedback.get("outcome_match", True))
    novelty_score = float((novelty or {}).get("novelty_score", 0.0))
    safety_mode = str(context.get("reasoning_parameters", {}).get("priority_mode", "normal")) == "safety"

    mode = "moderate"
    if mismatch and learning_score < 0.5:
        mode = "rapid"
    elif learning_score >= 0.85 and not mismatch and novelty_score < 0.4:
        mode = "stable"
    elif novelty_score >= 0.65:
        mode = "rapid"

    if safety_mode and mode == "rapid":
        mode = "moderate"

    rate = {"stable": 0.2, "moderate": 0.5, "rapid": 0.85}[mode]
    actions = {
        "set_profile": "strict" if mode == "stable" else ("balanced" if mode == "moderate" else "adaptive"),
        "set_mode": "stability" if mode != "rapid" else "exploration",
        "evolution_intensity": mode,
        "learning_adjustment": mode,
    }

    entry = {
        "learning_score": learning_score,
        "outcome_match": not mismatch,
        "novelty_score": novelty_score,
        "safety_mode": safety_mode,
        "mode": mode,
        "rate": rate,
        "actions": actions,
    }
    history = list(state.get("history", []))
    history.append(entry)
    state["history"] = history[-400:]
    state["last"] = entry
    state["mode"] = mode
    state["rate"] = rate
    _save(path, state)

    return {"ok": True, "mode": mode, "rate": rate, "actions": actions, "history_size": len(state["history"])}

