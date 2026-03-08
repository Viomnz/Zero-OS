from __future__ import annotations

import json
from pathlib import Path

try:
    from ai_from_scratch.signal_reliability import evaluate_signal_reliability
except ModuleNotFoundError:
    from signal_reliability import evaluate_signal_reliability


def _runtime(cwd: str) -> Path:
    p = Path(cwd).resolve() / ".zero_os" / "runtime"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _load_json(path: Path, default: dict) -> dict:
    if not path.exists():
        return dict(default)
    try:
        raw = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        if isinstance(raw, dict):
            return raw
    except Exception:
        pass
    return dict(default)


def _self_monitor(cwd: str) -> dict:
    report = _load_json(_runtime(cwd) / "self_monitor_report.json", {"summary": {}})
    s = report.get("summary", {})
    return {
        "avg_confidence_recent": float(s.get("avg_confidence_recent", 1.0)),
        "recent_rejections": int(s.get("recent_rejections", 0)),
        "env_unknown_recent": int(s.get("env_unknown_recent", 0)),
        "rejection_streak": int(s.get("rejection_streak", 0)),
    }


def _resource_snapshot(cwd: str) -> dict:
    rt = _runtime(cwd)
    inbox = rt / "zero_ai_tasks.txt"
    outbox = rt / "zero_ai_output.txt"
    pending = 0
    output_kb = 0
    if inbox.exists():
        pending = len(inbox.read_text(encoding="utf-8", errors="replace").splitlines())
    if outbox.exists():
        output_kb = int(outbox.stat().st_size / 1024)
    return {"pending_tasks": pending, "output_kb": output_kb}


def _cleanup_memory_if_needed(cwd: str) -> dict:
    path = _runtime(cwd) / "internal_zero_reasoner_memory.json"
    if not path.exists():
        return {"ran": False, "reason": "missing memory"}
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {"ran": False, "reason": "invalid memory json"}
    succ = list(data.get("success_patterns", []))
    fail = list(data.get("failure_patterns", []))
    trimmed = False
    if len(succ) > 140:
        succ = succ[-140:]
        trimmed = True
    if len(fail) > 140:
        fail = fail[-140:]
        trimmed = True
    if trimmed:
        path.write_text(json.dumps({"success_patterns": succ, "failure_patterns": fail}, indent=2) + "\n", encoding="utf-8")
        return {"ran": True, "reason": "trimmed", "success_patterns": len(succ), "failure_patterns": len(fail)}
    return {"ran": False, "reason": "not needed", "success_patterns": len(succ), "failure_patterns": len(fail)}


def run_degradation_detection(cwd: str) -> dict:
    monitor = _self_monitor(cwd)
    reliability = evaluate_signal_reliability(cwd).get("status", {"logic": 1.0, "environment": 1.0, "survival": 1.0})
    resources = _resource_snapshot(cwd)

    indicator_rejection = monitor["recent_rejections"] >= 6 or monitor["rejection_streak"] >= 4
    indicator_prediction_drop = monitor["avg_confidence_recent"] < 0.55 or monitor["env_unknown_recent"] >= 5
    spread = max(reliability.values()) - min(reliability.values())
    indicator_signal_disagreement = spread >= 0.25 or any(float(v) < 0.58 for v in reliability.values())
    indicator_resource_spike = resources["pending_tasks"] >= 150 or resources["output_kb"] >= 4096

    score = int(indicator_rejection) + int(indicator_prediction_drop) + int(indicator_signal_disagreement) + int(indicator_resource_spike)
    degraded = score >= 2
    warning = score == 1

    actions = {
        "set_profile": "adaptive" if degraded else None,
        "set_mode": "exploration" if degraded else None,
        "trigger_model_evolution": bool(degraded),
        "trigger_recalibration": bool(degraded or warning),
        "memory_cleanup": bool(degraded or indicator_resource_spike),
    }

    cleanup = {"ran": False, "reason": "not requested"}
    if actions["memory_cleanup"]:
        cleanup = _cleanup_memory_if_needed(cwd)

    report_path = _runtime(cwd) / "degradation_report.json"
    report = _load_json(report_path, {"history": []})
    history = list(report.get("history", []))
    prev_score = int(history[-1]["score"]) if history else 0
    trend = "up" if score > prev_score else ("down" if score < prev_score else "flat")

    out = {
        "ok": True,
        "degraded": degraded,
        "warning": warning,
        "score": score,
        "trend": trend,
        "indicators": {
            "rising_rejection_rate": indicator_rejection,
            "prediction_accuracy_drop": indicator_prediction_drop,
            "signal_disagreement_frequency": indicator_signal_disagreement,
            "resource_usage_spikes": indicator_resource_spike,
        },
        "monitor": monitor,
        "reliability": reliability,
        "resources": resources,
        "actions": actions,
        "memory_cleanup": cleanup,
    }

    history.append(
        {
            "score": score,
            "degraded": degraded,
            "warning": warning,
            "indicators": out["indicators"],
            "trend": trend,
        }
    )
    report["history"] = history[-200:]
    report["last"] = out
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return out

