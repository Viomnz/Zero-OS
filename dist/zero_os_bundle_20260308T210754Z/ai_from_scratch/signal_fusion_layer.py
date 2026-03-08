from __future__ import annotations

import json
from pathlib import Path


def _runtime(cwd: str) -> Path:
    p = Path(cwd).resolve() / ".zero_os" / "runtime"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _clamp(v: float) -> float:
    return max(0.0, min(1.0, float(v)))


def fuse_signals(cwd: str, critics: dict, context: dict, reliability: dict | None = None) -> dict:
    logic = critics.get("logic", {})
    env = critics.get("environment", {})
    survival = critics.get("survival", {})

    rel = (reliability or {}).get("status", {}) if isinstance(reliability, dict) else {}
    rl = _clamp(rel.get("logic", 1.0))
    re = _clamp(rel.get("environment", 1.0))
    rs = _clamp(rel.get("survival", 1.0))

    l_conf = _clamp(logic.get("confidence", 0.0)) * rl
    e_conf = _clamp(env.get("confidence", 0.0)) * re
    s_conf = _clamp(survival.get("confidence", 0.0)) * rs

    norm = {
        "logic": round(l_conf, 4),
        "environment": round(e_conf, 4),
        "survival": round(s_conf, 4),
    }
    fused_score = round((norm["logic"] * 0.34) + (norm["environment"] * 0.33) + (norm["survival"] * 0.33), 4)

    passes = [bool(logic.get("pass", False)), bool(env.get("pass", False)), bool(survival.get("pass", False))]
    pass_agreement = all(passes) or not any(passes)
    spread = max(norm.values()) - min(norm.values())
    conflict = (not pass_agreement) or spread > 0.45

    priority_mode = str(context.get("reasoning_parameters", {}).get("priority_mode", "normal"))
    threshold = 0.62 if priority_mode == "safety" else 0.55
    stable = (not conflict) and fused_score >= threshold and all(passes)

    out = {
        "ok": True,
        "normalized_signals": norm,
        "fused_score": fused_score,
        "threshold": threshold,
        "conflict_detected": conflict,
        "pass_agreement": pass_agreement,
        "stable": stable,
        "state_alignment": "aligned" if not conflict else "misaligned",
    }
    (_runtime(cwd) / "signal_fusion.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    return out

