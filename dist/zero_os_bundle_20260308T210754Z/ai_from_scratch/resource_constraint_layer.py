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


def evaluate_resource_constraints(cwd: str, prompt: str, gate, context: dict) -> dict:
    rt = _runtime(cwd)
    hist_path = rt / "resource_constraint_history.json"
    history = _load(hist_path, {"history": []})
    entries = list(history.get("history", []))[-400:]

    attempts_used = int(getattr(gate, "resource", {}).get("attempts_used", 1))
    attempt_limit = max(1, int(getattr(gate, "resource", {}).get("attempt_limit", attempts_used)))
    elapsed_ms = int(getattr(gate, "resource", {}).get("elapsed_ms", 0))
    deadline_ms = max(1, int(getattr(gate, "resource", {}).get("deadline_ms", 220)))

    compute_load = min(1.0, attempts_used / attempt_limit)
    memory_load = min(1.0, len(str(prompt or "")) / 4000.0)

    trace = _load(rt / "decision_trace.json", {"history": []})
    trace_size = len(list(trace.get("history", [])))
    storage_load = min(1.0, trace_size / 1200.0)

    # Approximate energy from compute intensity and elapsed ratio.
    elapsed_ratio = min(1.0, elapsed_ms / deadline_ms)
    energy_load = min(1.0, (compute_load * 0.6) + (elapsed_ratio * 0.4))

    pressure = round((compute_load * 0.35) + (memory_load * 0.25) + (storage_load * 0.2) + (energy_load * 0.2), 4)
    safety_mode = str(context.get("reasoning_parameters", {}).get("priority_mode", "normal")) == "safety"
    approve_threshold = 0.75 if safety_mode else 0.82
    delay_threshold = 0.92

    decision = "approve"
    if pressure > delay_threshold:
        decision = "reject"
    elif pressure > approve_threshold:
        decision = "delay"

    strategies = {
        "task_scheduling": decision in {"delay", "reject"},
        "priority_allocation": safety_mode,
        "load_balancing": compute_load > 0.7,
        "temporary_throttling": decision != "approve",
    }

    out = {
        "ok": True,
        "decision": decision,
        "resource_pressure": pressure,
        "thresholds": {"approve": approve_threshold, "delay": delay_threshold},
        "domains": {
            "compute": round(compute_load, 4),
            "memory": round(memory_load, 4),
            "storage": round(storage_load, 4),
            "energy": round(energy_load, 4),
        },
        "strategies": strategies,
    }

    entries.append({"prompt": str(prompt), "decision": decision, "pressure": pressure})
    history["history"] = entries[-400:]
    hist_path.write_text(json.dumps(history, indent=2) + "\n", encoding="utf-8")
    (rt / "resource_constraint.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    return out

