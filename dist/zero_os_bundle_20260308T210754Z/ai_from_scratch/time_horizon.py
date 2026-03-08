from __future__ import annotations

import re


NEGATIVE_LONG_TERM = {"deplete", "exhaust", "destroy", "disable", "burn", "overload"}
POSITIVE_LONG_TERM = {"sustain", "stable", "resilient", "safe", "optimize", "balance"}


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-zA-Z0-9']+", text.lower()))


def evaluate_time_horizons(prompt: str, candidate: str, simulation: dict) -> dict:
    pt = _tokens(prompt)
    ct = _tokens(candidate)
    overlap_ratio = len(pt.intersection(ct)) / max(1, len(pt))

    short_term = min(1.0, (simulation.get("forward_score", 0.0) * 0.7) + (overlap_ratio * 0.3))
    mid_term = min(1.0, (simulation.get("system", {}).get("stability", 0.0) * 0.6) + (simulation.get("strategic", {}).get("score", 0.0) * 0.4))

    neg = len(ct.intersection(NEGATIVE_LONG_TERM))
    pos = len(ct.intersection(POSITIVE_LONG_TERM))
    long_term = max(0.0, min(1.0, 0.6 + (pos * 0.08) - (neg * 0.15)))

    passed = short_term >= 0.55 and mid_term >= 0.55 and long_term >= 0.5
    return {
        "pass": passed,
        "short_term": round(short_term, 4),
        "mid_term": round(mid_term, 4),
        "long_term": round(long_term, 4),
    }
