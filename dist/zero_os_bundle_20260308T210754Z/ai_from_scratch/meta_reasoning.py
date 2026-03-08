from __future__ import annotations

import json
import re
from pathlib import Path


def _runtime(cwd: str) -> Path:
    p = Path(cwd).resolve() / ".zero_os" / "runtime"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-zA-Z0-9']+", str(text or "").lower()))


def _score_candidate(prompt: str, candidate: str) -> float:
    p = _tokens(prompt)
    c = _tokens(candidate)
    if not p or not c:
        return 0.0
    overlap = len(p.intersection(c)) / max(1, len(p))
    length_penalty = 0.0 if len(candidate) <= 900 else min(0.4, (len(candidate) - 900) / 3000)
    return max(0.0, min(1.0, overlap - length_penalty))


def run_meta_reasoning(cwd: str, prompt: str, candidates: list[str]) -> dict:
    ranked = sorted(
        [{"candidate": c, "score": round(_score_candidate(prompt, c), 4), "chars": len(c)} for c in candidates],
        key=lambda x: x["score"],
        reverse=True,
    )
    top = ranked[:9]
    avg_score = round(sum(x["score"] for x in top) / max(1, len(top)), 4)
    inefficient = avg_score < 0.45 or any(x["chars"] > 1800 for x in top)

    strategy = "balanced_path"
    if inefficient:
        strategy = "compressed_path"
    elif avg_score > 0.8:
        strategy = "fast_path"

    errors = []
    if avg_score < 0.35:
        errors.append("low_prompt_alignment")
    if any(x["chars"] > 1800 for x in top):
        errors.append("verbose_candidate_pattern")

    out = {
        "ok": True,
        "strategy": strategy,
        "reasoning_analysis": {
            "average_alignment_score": avg_score,
            "inefficient_path": inefficient,
            "candidate_count": len(candidates),
        },
        "error_patterns": errors,
        "ranked": top,
    }
    (_runtime(cwd) / "meta_reasoning_report.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    return out

