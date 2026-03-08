from __future__ import annotations

import json
from pathlib import Path

try:
    from ai_from_scratch.signal_reliability import apply_reliability_calibration, evaluate_signal_reliability
except ModuleNotFoundError:
    from signal_reliability import apply_reliability_calibration, evaluate_signal_reliability


def _runtime(cwd: str) -> Path:
    p = Path(cwd).resolve() / ".zero_os" / "runtime"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _self_monitor_summary(cwd: str) -> dict:
    p = _runtime(cwd) / "self_monitor_report.json"
    if not p.exists():
        return {"avg_confidence_recent": 1.0, "recent_rejections": 0, "env_unknown_recent": 0}
    try:
        raw = json.loads(p.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {"avg_confidence_recent": 1.0, "recent_rejections": 0, "env_unknown_recent": 0}
    summary = raw.get("summary", {})
    return {
        "avg_confidence_recent": float(summary.get("avg_confidence_recent", 1.0)),
        "recent_rejections": int(summary.get("recent_rejections", 0)),
        "env_unknown_recent": int(summary.get("env_unknown_recent", 0)),
    }


def run_calibration(cwd: str) -> dict:
    reliability = evaluate_signal_reliability(cwd)
    monitor = _self_monitor_summary(cwd)
    status = reliability["status"]

    targets = {
        "logic": 0.92,
        "environment": 0.9,
        "survival": 0.92,
    }
    if status["environment"] < 0.6 or monitor["env_unknown_recent"] >= 4:
        targets["environment"] = 0.96
    if monitor["avg_confidence_recent"] < 0.6 or monitor["recent_rejections"] >= 4:
        targets["logic"] = 0.95
        targets["survival"] = 0.95

    adjust = apply_reliability_calibration(cwd, targets, strength=0.12)

    actions = {"set_profile": None, "set_mode": None}
    if monitor["recent_rejections"] >= 5 or status["environment"] < 0.55:
        actions["set_profile"] = "adaptive"
        actions["set_mode"] = "exploration"
    elif monitor["avg_confidence_recent"] >= 0.85 and status["logic"] >= 0.85 and status["survival"] >= 0.85:
        actions["set_profile"] = "balanced"
        actions["set_mode"] = "stability"

    out = {
        "ok": True,
        "reliability_before": status,
        "targets": targets,
        "reliability_after": adjust["current"],
        "monitor_feedback": monitor,
        "actions": actions,
    }
    (_runtime(cwd) / "calibration_state.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    return out

