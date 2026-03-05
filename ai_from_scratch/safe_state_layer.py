from __future__ import annotations

import json
from pathlib import Path


def _runtime(cwd: str) -> Path:
    p = Path(cwd).resolve() / ".zero_os" / "runtime"
    p.mkdir(parents=True, exist_ok=True)
    return p


def evaluate_safe_state(cwd: str, gate, degradation: dict, calibration: dict) -> dict:
    consensus_failure = not bool(getattr(gate, "accepted", False))
    fallback_mode = str(getattr(gate, "fallback_mode", ""))
    resource = dict(getattr(gate, "resource", {}) or {})
    time_abort = bool(resource.get("time_abort", False))
    attempts_used = int(resource.get("attempts_used", 0))
    attempt_limit = int(resource.get("attempt_limit", 0))

    degradation_score = int(degradation.get("score", 0))
    degraded = bool(degradation.get("degraded", False))
    calibration_actions = calibration.get("actions", {}) if isinstance(calibration, dict) else {}

    triggers = {
        "repeated_consensus_failure": consensus_failure and fallback_mode in {"best_available", "signal_reliability_block"},
        "critical_signal_corruption": fallback_mode in {"signal_reliability_block", "core_rule_violation"},
        "resource_exhaustion": time_abort or (attempt_limit > 0 and attempts_used >= attempt_limit),
        "severe_degradation": degraded and degradation_score >= 3,
    }
    enter_safe_state = any(triggers.values())

    if enter_safe_state:
        action = "pause_execution"
        if triggers["critical_signal_corruption"]:
            action = "return_to_baseline"
        elif triggers["severe_degradation"]:
            action = "request_external_input"
    else:
        action = "continue"

    out = {
        "enter_safe_state": enter_safe_state,
        "action": action,
        "triggers": triggers,
        "fallback_mode": fallback_mode,
        "resource": resource,
        "degradation_score": degradation_score,
        "calibration_actions": calibration_actions,
    }
    (_runtime(cwd) / "safe_state_report.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    return out

