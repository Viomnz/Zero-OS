from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from zero_os.self_continuity import zero_ai_self_continuity_update


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _runtime_snapshot_path(cwd: str) -> Path:
    path = Path(cwd).resolve() / ".zero_os" / "runtime"
    path.mkdir(parents=True, exist_ok=True)
    return path / "zero_ai_identity_snapshot.json"


def zero_ai_identity(cwd: str | None = None) -> dict:
    out = {
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
    if cwd:
        _runtime_snapshot_path(cwd).write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
        continuity = zero_ai_self_continuity_update(cwd)
        out["self_continuity"] = {
            "continuity_score": continuity.get("continuity", {}).get("continuity_score"),
            "same_system": continuity.get("continuity", {}).get("same_system"),
            "has_contradiction": continuity.get("contradiction_detection", {}).get("has_contradiction"),
        }
    return out
