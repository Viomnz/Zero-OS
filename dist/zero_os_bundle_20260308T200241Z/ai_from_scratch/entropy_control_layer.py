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


def _save(path: Path, payload) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _dedupe_history(entries: list[dict], key_fn) -> list[dict]:
    seen = set()
    out: list[dict] = []
    for item in reversed(entries):
        key = key_fn(item)
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    out.reverse()
    return out


def control_entropy(cwd: str, threshold: float = 0.55) -> dict:
    rt = _runtime(cwd)
    learning_path = rt / "learning_feedback.json"
    trace_path = rt / "decision_trace.json"
    knowledge_path = rt / "knowledge_model.json"

    learning = _load(learning_path, {"history": []})
    trace = _load(trace_path, {"history": []})
    knowledge = _load(knowledge_path, {"sources": [], "last": {}})

    learning_hist = list(learning.get("history", []))
    trace_hist = list(trace.get("history", []))
    sources = list(knowledge.get("sources", []))

    # Entropy indicators
    fragmented_knowledge = len({str(s.get("source", "")) for s in sources if isinstance(s, dict)}) > 3
    redundant_learning = len(learning_hist) > 0 and len(_dedupe_history(
        learning_hist,
        lambda x: (
            str(x.get("prompt", "")).strip().lower(),
            bool(x.get("outcome_match", False)),
            round(float(x.get("learning_score", 0.0)), 2),
        ),
    )) / max(1, len(learning_hist)) < 0.7
    redundant_trace = len(trace_hist) > 0 and len(_dedupe_history(
        trace_hist,
        lambda x: (
            str(x.get("input", {}).get("prompt", "")).strip().lower(),
            bool(x.get("final_action", {}).get("execute", False)),
        ),
    )) / max(1, len(trace_hist)) < 0.7

    entropy_level = 0.0
    if fragmented_knowledge:
        entropy_level += 0.34
    if redundant_learning:
        entropy_level += 0.33
    if redundant_trace:
        entropy_level += 0.33
    entropy_level = round(min(1.0, entropy_level), 4)

    actions = {
        "knowledge_reorganization": False,
        "model_simplification": False,
        "memory_restructuring": False,
    }
    if entropy_level > float(threshold):
        actions["knowledge_reorganization"] = True
        actions["model_simplification"] = True
        actions["memory_restructuring"] = True

        # Apply lightweight in-place reorganization.
        learning["history"] = _dedupe_history(
            learning_hist,
            lambda x: (
                str(x.get("prompt", "")).strip().lower(),
                bool(x.get("outcome_match", False)),
                round(float(x.get("learning_score", 0.0)), 2),
            ),
        )[-300:]
        if learning["history"]:
            learning["last"] = learning["history"][-1]

        trace["history"] = _dedupe_history(
            trace_hist,
            lambda x: (
                str(x.get("input", {}).get("prompt", "")).strip().lower(),
                bool(x.get("final_action", {}).get("execute", False)),
            ),
        )[-300:]
        if trace["history"]:
            trace["last"] = trace["history"][-1]

        unique_sources = []
        seen_src = set()
        for s in sources:
            key = (str(s.get("source", "")).strip().lower(), str(s.get("type", "")).strip().lower())
            if key in seen_src:
                continue
            seen_src.add(key)
            unique_sources.append(s)
        knowledge["sources"] = unique_sources[:20]

        _save(learning_path, learning)
        _save(trace_path, trace)
        _save(knowledge_path, knowledge)

    out = {
        "ok": True,
        "entropy_level": entropy_level,
        "threshold": float(threshold),
        "indicators": {
            "fragmented_knowledge": fragmented_knowledge,
            "redundant_learning_paths": redundant_learning,
            "memory_disorder": redundant_trace,
        },
        "actions": actions,
    }
    _save(rt / "entropy_control.json", out)
    return out

