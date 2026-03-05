from __future__ import annotations

import json
from collections import Counter
from pathlib import Path


def _runtime(cwd: str) -> Path:
    p = Path(cwd).resolve() / ".zero_os" / "runtime"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return default


def _save_json(path: Path, payload) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _dedupe_by_key(items: list[dict], key_fn) -> list[dict]:
    seen = set()
    out: list[dict] = []
    for item in reversed(items):
        key = key_fn(item)
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    out.reverse()
    return out


def run_compression(cwd: str, threshold_entries: int = 300) -> dict:
    rt = _runtime(cwd)
    lf_path = rt / "learning_feedback.json"
    dt_path = rt / "decision_trace.json"

    learning = _load_json(lf_path, {"history": [], "stats": {}})
    trace = _load_json(dt_path, {"history": []})

    lf_history = list(learning.get("history", []))
    dt_history = list(trace.get("history", []))

    before = {"learning_feedback": len(lf_history), "decision_trace": len(dt_history)}

    compressed_lf = _dedupe_by_key(
        lf_history,
        lambda x: (
            str(x.get("prompt", "")).strip().lower(),
            bool(x.get("outcome_match", False)),
            round(float(x.get("learning_score", 0.0)), 2),
        ),
    )
    compressed_dt = _dedupe_by_key(
        dt_history,
        lambda x: (
            str(x.get("input", {}).get("prompt", "")).strip().lower(),
            bool(x.get("consensus", {}).get("accepted", False)),
            bool(x.get("final_action", {}).get("execute", False)),
        ),
    )

    if len(compressed_lf) > threshold_entries:
        compressed_lf = compressed_lf[-threshold_entries:]
    if len(compressed_dt) > threshold_entries:
        compressed_dt = compressed_dt[-threshold_entries:]

    learning["history"] = compressed_lf
    if compressed_lf:
        learning["last"] = compressed_lf[-1]
    trace["history"] = compressed_dt
    if compressed_dt:
        trace["last"] = compressed_dt[-1]

    _save_json(lf_path, learning)
    _save_json(dt_path, trace)

    prompt_counter = Counter(str(x.get("prompt", "")).strip().lower() for x in compressed_lf if x.get("prompt"))
    decision_counter = Counter(str(x.get("input", {}).get("prompt", "")).strip().lower() for x in compressed_dt)
    summary = {
        "top_learning_patterns": [{"prompt": p, "count": c} for p, c in prompt_counter.most_common(5)],
        "top_decision_patterns": [{"prompt": p, "count": c} for p, c in decision_counter.most_common(5)],
        "essential_conclusions": {
            "learning_entries": len(compressed_lf),
            "decision_entries": len(compressed_dt),
            "dedupe_active": True,
        },
    }

    report = {
        "ok": True,
        "threshold_entries": int(threshold_entries),
        "before": before,
        "after": {"learning_feedback": len(compressed_lf), "decision_trace": len(compressed_dt)},
        "removed": {
            "learning_feedback": before["learning_feedback"] - len(compressed_lf),
            "decision_trace": before["decision_trace"] - len(compressed_dt),
        },
        "summary": summary,
    }
    _save_json(rt / "compression_simplification.json", report)
    return report

