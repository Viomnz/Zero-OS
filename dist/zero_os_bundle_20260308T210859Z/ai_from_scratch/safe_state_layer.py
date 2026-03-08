from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


def _runtime(cwd: str) -> Path:
    p = Path(cwd).resolve() / ".zero_os" / "runtime"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return default


def _save(path: Path, payload) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def evaluate_safe_state(cwd: str, gate, degradation: dict, calibration: dict) -> dict:
    rt = _runtime(cwd)
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
    state_path = rt / "safe_mode_state.json"
    state = _load(
        state_path,
        {
            "mode": "normal",
            "entered_count": 0,
            "last_entered_utc": "",
            "last_recovered_utc": "",
            "last_reason": "",
            "history": [],
        },
    )

    enter_safe_state = any(triggers.values())

    if enter_safe_state:
        action = "pause_execution"
        if triggers["critical_signal_corruption"]:
            action = "return_to_baseline"
        elif triggers["severe_degradation"]:
            action = "request_external_input"
        controlled_mode = {
            "halt_non_critical_processes": True,
            "restrict_actions": True,
            "preserve_core_data": True,
            "activate_diagnostics": True,
        }
        diagnostics = {
            "reason": "safe_state_entered",
            "fallback_mode": fallback_mode,
            "attempts_used": attempts_used,
            "attempt_limit": attempt_limit,
            "time_abort": time_abort,
            "degradation_score": degradation_score,
            "calibration_actions": calibration_actions,
        }
        state["mode"] = "safe"
        state["entered_count"] = int(state.get("entered_count", 0)) + 1
        state["last_entered_utc"] = _utc_now()
        state["last_reason"] = action
        state["history"] = list(state.get("history", []))[-199:] + [
            {"time_utc": state["last_entered_utc"], "event": "enter", "action": action, "triggers": triggers}
        ]
    else:
        action = "continue"
        controlled_mode = {
            "halt_non_critical_processes": False,
            "restrict_actions": False,
            "preserve_core_data": True,
            "activate_diagnostics": False,
        }
        diagnostics = {"reason": "stable"}
        if state.get("mode") == "safe":
            state["last_recovered_utc"] = _utc_now()
            state["history"] = list(state.get("history", []))[-199:] + [
                {"time_utc": state["last_recovered_utc"], "event": "recover", "action": "resume"}
            ]
        state["mode"] = "normal"

    out = {
        "enter_safe_state": enter_safe_state,
        "action": action,
        "triggers": triggers,
        "fallback_mode": fallback_mode,
        "resource": resource,
        "degradation_score": degradation_score,
        "calibration_actions": calibration_actions,
        "controlled_mode": controlled_mode,
        "diagnostics": diagnostics,
        "recovery_process": {
            "stabilize_system": enter_safe_state,
            "diagnose_failure": enter_safe_state,
            "repair_components": action in {"return_to_baseline", "request_external_input"},
            "resume_operation": not enter_safe_state,
        },
        "state": {
            "mode": state.get("mode", "normal"),
            "entered_count": int(state.get("entered_count", 0)),
            "last_entered_utc": state.get("last_entered_utc", ""),
            "last_recovered_utc": state.get("last_recovered_utc", ""),
            "last_reason": state.get("last_reason", ""),
        },
    }
    _save(state_path, state)
    _save(rt / "safe_state_report.json", out)
    return out
