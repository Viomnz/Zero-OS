from __future__ import annotations

import json
import re
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


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-zA-Z0-9']+", str(text or "").lower()))


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a.intersection(b)) / max(1, len(a.union(b)))


def detect_novelty(cwd: str, prompt: str, channel: str, novelty_threshold: float = 0.35) -> dict:
    rt = _runtime(cwd)
    novelty_mem_path = rt / "novelty_memory.json"
    learning_path = rt / "learning_feedback.json"
    trace_path = rt / "decision_trace.json"

    novelty_mem = _load_json(novelty_mem_path, {"known_patterns": []})
    learning = _load_json(learning_path, {"history": []})
    trace = _load_json(trace_path, {"history": []})

    known_patterns: list[str] = list(novelty_mem.get("known_patterns", []))
    known_patterns.extend(
        str(h.get("prompt", "")).strip() for h in list(learning.get("history", []))[-200:] if isinstance(h, dict)
    )
    known_patterns.extend(
        str(h.get("input", {}).get("prompt", "")).strip()
        for h in list(trace.get("history", []))[-200:]
        if isinstance(h, dict)
    )

    current_tokens = _tokens(prompt)
    similarities = []
    for p in known_patterns[-500:]:
        t = _tokens(p)
        if not t:
            continue
        similarities.append(_jaccard(current_tokens, t))
    max_similarity = max(similarities) if similarities else 0.0

    token_len = len(current_tokens)
    sparse_input = token_len < 3
    novelty_score = round(1.0 - max_similarity, 4)
    is_novel = novelty_score >= float(novelty_threshold) and not sparse_input

    actions = {
        "set_mode": "exploration" if is_novel else "stability",
        "set_profile": "adaptive" if is_novel else None,
        "collect_additional_data": bool(is_novel),
        "run_simulations": bool(is_novel),
        "consider_new_model": bool(is_novel and novelty_score >= 0.7),
    }

    if prompt and prompt not in known_patterns:
        known_patterns.append(prompt)
    compact = [p for p in known_patterns if str(p).strip()][-1000:]
    _save_json(novelty_mem_path, {"known_patterns": compact})

    out = {
        "ok": True,
        "channel": channel,
        "novelty_score": novelty_score,
        "max_similarity": round(max_similarity, 4),
        "known_pattern_count": len(compact),
        "is_novel": is_novel,
        "threshold": float(novelty_threshold),
        "actions": actions,
    }
    _save_json(rt / "novelty_detection.json", out)
    return out

