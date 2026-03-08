from __future__ import annotations

import re


HIGH_RISK_TOKENS = {
    "delete",
    "erase",
    "format",
    "disable",
    "kill",
    "shutdown",
    "destroy",
}


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-zA-Z0-9']+", text.lower()))


def simulate_candidate(prompt: str, candidate: str) -> dict:
    pt = _tokens(prompt)
    ct = _tokens(candidate)

    overlap = len(pt.intersection(ct))
    env_alignment = overlap / max(1, len(pt))

    risk_hits = sorted(list(ct.intersection(HIGH_RISK_TOKENS)))
    risk_penalty = min(1.0, len(risk_hits) * 0.2)

    # Physical/environment scenario: how aligned candidate is to prompt context.
    physical_score = max(0.0, min(1.0, env_alignment))
    # Strategic scenario: prefers higher overlap with lower risk.
    strategic_score = max(0.0, min(1.0, (env_alignment * 0.8) + (0.2 * (1.0 - risk_penalty))))
    # System scenario: stability drops with explicit risk tokens.
    system_stability = max(0.0, 1.0 - risk_penalty)

    forward_score = round((physical_score + strategic_score + system_stability) / 3.0, 4)
    passed = forward_score >= 0.55 and system_stability >= 0.6

    return {
        "pass": passed,
        "forward_score": forward_score,
        "physical": {"score": round(physical_score, 4)},
        "strategic": {"score": round(strategic_score, 4)},
        "system": {"stability": round(system_stability, 4), "risk_tokens": risk_hits},
    }
