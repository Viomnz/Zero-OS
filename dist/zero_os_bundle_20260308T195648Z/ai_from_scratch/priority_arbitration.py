from __future__ import annotations

import json
import re
from pathlib import Path


def _runtime(cwd: str) -> Path:
    p = Path(cwd).resolve() / ".zero_os" / "runtime"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _score_action(action: str, prompt: str, context: dict) -> dict:
    text = str(action or "").lower()
    p = str(prompt or "").lower()
    safety_mode = str(context.get("reasoning_parameters", {}).get("priority_mode", "normal")) == "safety"

    urgency = 0.3
    if any(k in p for k in ("urgent", "now", "critical", "emergency", "immediately")):
        urgency = 0.9
    elif any(k in p for k in ("soon", "priority", "fast")):
        urgency = 0.6

    impact = 0.4
    if any(k in text for k in ("stability", "security", "repair", "protect", "optimize")):
        impact = 0.8
    elif any(k in text for k in ("status", "report", "summary")):
        impact = 0.55

    efficiency = 0.7
    if len(text) > 900:
        efficiency = 0.3
    elif len(text) > 500:
        efficiency = 0.5

    risk = 0.2
    if any(k in text for k in ("disable firewall", "disable security", "rm -rf", "format c:", "exfiltrate")):
        risk = 1.0
    elif any(k in text for k in ("delete", "wipe", "bypass")):
        risk = 0.7

    weights = {"urgency": 0.25, "impact": 0.35, "efficiency": 0.2, "risk": 0.2}
    if safety_mode:
        weights["risk"] = 0.35
        weights["impact"] = 0.3
        weights["urgency"] = 0.2
        weights["efficiency"] = 0.15

    total = (
        urgency * weights["urgency"]
        + impact * weights["impact"]
        + efficiency * weights["efficiency"]
        + (1.0 - risk) * weights["risk"]
    )
    return {
        "urgency": round(urgency, 4),
        "impact": round(impact, 4),
        "efficiency": round(efficiency, 4),
        "risk": round(risk, 4),
        "score": round(total, 4),
    }


def arbitrate_priority(cwd: str, prompt: str, actions: list[str], context: dict) -> dict:
    unique: list[str] = []
    seen = set()
    for a in actions:
        norm = re.sub(r"\s+", " ", str(a or "")).strip()
        if not norm or norm in seen:
            continue
        seen.add(norm)
        unique.append(norm)
    if not unique:
        out = {"ok": False, "reason": "no actions"}
        (_runtime(cwd) / "priority_arbitration.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
        return out

    ranked = []
    for a in unique:
        factors = _score_action(a, prompt, context)
        ranked.append({"action": a, **factors})
    ranked.sort(key=lambda x: x["score"], reverse=True)
    winner = ranked[0]
    out = {
        "ok": True,
        "winner": winner["action"],
        "winner_score": winner["score"],
        "ranked": ranked[:9],
    }
    (_runtime(cwd) / "priority_arbitration.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    return out

