from __future__ import annotations

import json
from collections import Counter
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


def detect_emergent_patterns(cwd: str, prompt: str, context: dict, knowledge: dict) -> dict:
    rt = _runtime(cwd)
    lf = _load(rt / "learning_feedback.json", {"history": []})
    dt = _load(rt / "decision_trace.json", {"history": []})

    learning_hist = list(lf.get("history", []))[-300:]
    trace_hist = list(dt.get("history", []))[-300:]

    prompt_counter = Counter(str(h.get("prompt", "")).strip().lower() for h in learning_hist if h.get("prompt"))
    mismatch_rate = 0.0
    if learning_hist:
        mismatch_rate = sum(1 for h in learning_hist if not bool(h.get("outcome_match", True))) / len(learning_hist)

    execute_counter = Counter(
        bool(h.get("final_action", {}).get("execute", False))
        for h in trace_hist
        if isinstance(h, dict)
    )
    execute_rate = 0.0
    if trace_hist:
        execute_rate = execute_counter.get(True, 0) / len(trace_hist)

    repeated_prompts = [{"prompt": p, "count": c} for p, c in prompt_counter.most_common(5) if c >= 3]
    patterns = []
    if repeated_prompts:
        patterns.append("behavioral_repetition")
    if mismatch_rate >= 0.4:
        patterns.append("feedback_drift")
    if execute_rate <= 0.35 and len(trace_hist) >= 15:
        patterns.append("low_execution_trend")

    priority_mode = str(context.get("reasoning_parameters", {}).get("priority_mode", "normal"))
    knowledge_variants = int(knowledge.get("unified_model", {}).get("source_count", 1))
    if knowledge_variants >= 2 and priority_mode == "normal":
        patterns.append("multi_source_context_shift")

    actions = {
        "set_profile": "adaptive" if ("feedback_drift" in patterns or "low_execution_trend" in patterns) else None,
        "set_mode": "exploration" if "multi_source_context_shift" in patterns else None,
        "update_knowledge_model": bool(patterns),
    }

    out = {
        "ok": True,
        "prompt": prompt,
        "patterns": patterns,
        "repeated_prompts": repeated_prompts,
        "metrics": {
            "mismatch_rate": round(mismatch_rate, 4),
            "execute_rate": round(execute_rate, 4),
            "history_size_learning": len(learning_hist),
            "history_size_trace": len(trace_hist),
        },
        "actions": actions,
    }
    (rt / "emergent_patterns.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    return out

