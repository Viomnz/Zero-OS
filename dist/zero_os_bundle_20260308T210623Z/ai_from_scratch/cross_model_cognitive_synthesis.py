from __future__ import annotations

import json
from pathlib import Path


def _runtime(cwd: str) -> Path:
    p = Path(cwd).resolve() / ".zero_os" / "runtime"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _normalize(s: str) -> str:
    return " ".join(str(s or "").strip().split())


def synthesize_cross_model_output(cwd: str, prompt: str, model_outputs: dict[str, str]) -> dict:
    weights = {
        "symbolic": 1.2,
        "neural": 1.0,
        "probabilistic": 1.1,
        "simulation": 1.1,
        "distributed": 1.25,
        "meta": 1.05,
    }
    ranked = []
    for name, text in model_outputs.items():
        out = _normalize(text)
        if not out:
            continue
        score = weights.get(name, 1.0)
        if any(k in out.lower() for k in ("stable", "safety", "secure", "balance", "survival")):
            score += 0.15
        if len(out) > 900:
            score -= 0.2
        ranked.append({"model": name, "output": out, "score": round(score, 4)})

    ranked.sort(key=lambda x: x["score"], reverse=True)
    unique = []
    seen = set()
    for item in ranked:
        key = item["output"].lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)

    top = unique[:3]
    conflict = len({x["output"] for x in top}) > 1 if top else False
    unified = top[0]["output"] if top else ""
    report = {
        "ok": bool(unified),
        "prompt": prompt,
        "models_seen": list(model_outputs.keys()),
        "ranked": unique[:9],
        "conflict_detected": conflict,
        "consensus_model": top[0]["model"] if top else "none",
        "unified_output": unified,
    }
    (_runtime(cwd) / "cross_model_cognitive_synthesis.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    return report

