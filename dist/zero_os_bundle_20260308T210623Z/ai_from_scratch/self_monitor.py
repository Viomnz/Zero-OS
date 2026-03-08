from __future__ import annotations

import json
from pathlib import Path


def _report_path(cwd: str) -> Path:
    p = Path(cwd).resolve() / ".zero_os" / "runtime" / "self_monitor_report.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _load_report(cwd: str) -> dict:
    p = _report_path(cwd)
    if not p.exists():
        return {"history": []}
    try:
        raw = json.loads(p.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {"history": []}
    if not isinstance(raw, dict):
        return {"history": []}
    return {"history": list(raw.get("history", []))[-400:]}


def _save_report(cwd: str, report: dict) -> None:
    _report_path(cwd).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


def update_self_monitor(
    cwd: str,
    accepted: bool,
    trace: list[dict],
    profile: str,
    mode: str,
    model_generation: int,
) -> dict:
    report = _load_report(cwd)
    history = report["history"]
    if trace:
        last = trace[-1]
        critics = last.get("critics", {})
        entry = {
            "accepted": bool(accepted),
            "combined_confidence": float(last.get("combined_confidence", 0.0)),
            "logic_conf": float(critics.get("logic", {}).get("confidence", 0.0)),
            "env_status": str(critics.get("environment", {}).get("status", "unknown")),
            "env_conf": float(critics.get("environment", {}).get("confidence", 0.0)),
            "survival_conf": float(critics.get("survival", {}).get("confidence", 0.0)),
            "profile": profile,
            "mode": mode,
            "model_generation": int(model_generation),
        }
        history.append(entry)
    history = history[-300:]
    report["history"] = history

    recent = history[-20:] if history else []
    reject_count = sum(1 for h in recent if not h["accepted"])
    env_unknown_count = sum(1 for h in recent if h.get("env_status") == "unknown")
    avg_conf = sum(float(h.get("combined_confidence", 0.0)) for h in recent) / max(1, len(recent))

    rejection_streak = 0
    for h in reversed(history):
        if h["accepted"]:
            break
        rejection_streak += 1

    drift_detected = avg_conf < 0.45
    signal_reliability = {
        "logic": round(sum(float(h.get("logic_conf", 0.0)) for h in recent) / max(1, len(recent)), 4),
        "environment": round(sum(float(h.get("env_conf", 0.0)) for h in recent) / max(1, len(recent)), 4),
        "survival": round(sum(float(h.get("survival_conf", 0.0)) for h in recent) / max(1, len(recent)), 4),
    }

    actions = {
        "set_profile": None,
        "set_mode": None,
        "trigger_new_model_generation": rejection_streak >= 4,
    }
    if drift_detected and profile == "strict":
        actions["set_profile"] = "balanced"
    if env_unknown_count >= 6 and mode == "stability":
        actions["set_mode"] = "exploration"
    elif env_unknown_count <= 1 and mode == "exploration":
        actions["set_mode"] = "stability"

    summary = {
        "avg_confidence_recent": round(avg_conf, 4),
        "recent_rejections": int(reject_count),
        "rejection_streak": int(rejection_streak),
        "env_unknown_recent": int(env_unknown_count),
        "drift_detected": bool(drift_detected),
        "signal_reliability": signal_reliability,
        "actions": actions,
    }
    report["summary"] = summary
    _save_report(cwd, report)
    return summary
