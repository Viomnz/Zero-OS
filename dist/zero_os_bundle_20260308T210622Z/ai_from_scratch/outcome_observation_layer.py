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


def observe_outcome(
    cwd: str,
    prompt: str,
    execution: dict,
    gate,
    context: dict,
) -> dict:
    rt = _runtime(cwd)
    trace = _load(rt / "decision_trace.json", {"history": []})
    recent = list(trace.get("history", []))[-30:]

    dispatch = execution.get("dispatch", {})
    executed = bool(execution.get("executed", False))
    actual_success = executed and bool(dispatch.get("allowed", False))

    attempts_used = max(1, int(getattr(gate, "resource", {}).get("attempts_used", 1)))
    attempt_limit = max(1, int(getattr(gate, "resource", {}).get("attempt_limit", attempts_used)))
    efficiency = max(0.0, 1.0 - (attempts_used - 1) / attempt_limit)

    repeated_prompt_count = sum(
        1 for item in recent if str(item.get("input", {}).get("prompt", "")).strip().lower() == prompt.strip().lower()
    )
    side_effects = repeated_prompt_count >= 8

    stability_impact = 1.0
    if side_effects:
        stability_impact -= 0.35
    if not actual_success:
        stability_impact -= 0.4
    stability_impact = round(max(0.0, stability_impact), 4)

    signal_rel = float(getattr(gate, "self_monitor", {}).get("avg_confidence_recent", 0.0))

    out = {
        "ok": True,
        "actual_success": actual_success,
        "metrics": {
            "success_rate": 1.0 if actual_success else 0.0,
            "side_effects": side_effects,
            "efficiency": round(efficiency, 4),
            "stability_impact": stability_impact,
        },
        "observed": {
            "actual_success": actual_success,
            "efficiency_score": round(efficiency, 4),
            "signal_reliability": round(signal_rel, 4),
            "stability_impact": stability_impact,
        },
        "context_mode": str(context.get("reasoning_parameters", {}).get("priority_mode", "normal")),
    }
    (rt / "outcome_observation.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    return out

