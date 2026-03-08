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


def monitor_system_health(cwd: str, prompt: str, gate, context: dict) -> dict:
    rt = _runtime(cwd)
    trace = _load(rt / "decision_trace.json", {"history": []})
    mem = _load(rt / "internal_zero_reasoner_memory.json", {"success_patterns": [], "failure_patterns": []})

    recent = list(trace.get("history", []))[-40:]
    repeated_prompt = sum(1 for h in recent if str(h.get("input", {}).get("prompt", "")).strip().lower() == prompt.strip().lower())
    behavior_anomaly = repeated_prompt >= 8

    avg_conf = float(getattr(gate, "self_monitor", {}).get("avg_confidence_recent", 0.0))
    processing_health = max(0.0, min(1.0, avg_conf))

    mem_ok = isinstance(mem.get("success_patterns", []), list) and isinstance(mem.get("failure_patterns", []), list)
    memory_health = 1.0 if mem_ok else 0.0

    attempts_used = int(getattr(gate, "resource", {}).get("attempts_used", 1))
    attempt_limit = max(1, int(getattr(gate, "resource", {}).get("attempt_limit", attempts_used)))
    resource_pressure = attempts_used / attempt_limit
    resource_health = max(0.0, 1.0 - resource_pressure)

    health_score = round((processing_health * 0.35) + (memory_health * 0.3) + (resource_health * 0.25) + ((0.0 if behavior_anomaly else 1.0) * 0.1), 4)
    acceptable = 0.58 if str(context.get("reasoning_parameters", {}).get("priority_mode", "normal")) == "safety" else 0.52
    healthy = health_score >= acceptable and mem_ok

    responses = {
        "diagnostic_scan": not healthy,
        "component_reset": not mem_ok,
        "load_redistribution": resource_pressure > 0.8,
        "temporary_restriction": behavior_anomaly or resource_pressure > 0.92,
    }

    out = {
        "ok": True,
        "healthy": healthy,
        "health_score": health_score,
        "threshold": acceptable,
        "domains": {
            "processing_health": round(processing_health, 4),
            "memory_health": round(memory_health, 4),
            "resource_usage_health": round(resource_health, 4),
            "decision_pattern_health": 0.0 if behavior_anomaly else 1.0,
        },
        "signals": {
            "performance_drop": processing_health < 0.45,
            "error_frequency": bool(getattr(gate, "self_monitor", {}).get("rejection_streak", 0) >= 4),
            "resource_pressure": resource_pressure > 0.8,
            "behavior_anomalies": behavior_anomaly,
        },
        "responses": responses,
    }
    (rt / "self_monitoring_layer.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    return out

