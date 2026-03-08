from __future__ import annotations

from datetime import datetime, timezone


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def zero_ai_identity() -> dict:
    return {
        "ok": True,
        "time_utc": _utc_now(),
        "classification": "recursion_filtration_engine",
        "is_rsi": False,
        "goals": {
            "primary": "stability",
            "secondary": "coherence",
            "constraints": ["survival_first", "anti_drift", "anti_contradiction"],
        },
        "rsi_contrast": {
            "rsi_focus": "capability_growth",
            "zero_ai_focus": "stability_filtration",
            "rsi_direction": "expand_complexity",
            "zero_ai_direction": "compress_to_stable_core",
        },
        "statement": "Zero-AI is a filtration engine, not a self-mutation engine.",
    }

