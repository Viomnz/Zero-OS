from __future__ import annotations

import json
from pathlib import Path

try:
    from ai_from_scratch.core_rule_layer import verify_core_rules
except ModuleNotFoundError:
    from core_rule_layer import verify_core_rules


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


def enforce_stability(cwd: str, prompt: str, final_output: str, gate, context: dict) -> dict:
    rt = _runtime(cwd)
    hist_path = rt / "stability_history.json"
    history = _load(hist_path, {"actions": []})
    actions = list(history.get("actions", []))[-300:]

    core = verify_core_rules(cwd)
    attempts_used = int(getattr(gate, "resource", {}).get("attempts_used", 1))
    attempt_limit = max(1, int(getattr(gate, "resource", {}).get("attempt_limit", attempts_used)))
    resource_pressure = attempts_used / attempt_limit

    recent = actions[-20:]
    same_output_count = sum(1 for a in recent if str(a.get("output", "")).strip() == str(final_output).strip() and final_output)
    oscillation_risk = same_output_count >= 7

    safety_mode = str(context.get("reasoning_parameters", {}).get("priority_mode", "normal")) == "safety"
    threshold = 0.62 if safety_mode else 0.72
    stability_score = 1.0
    if not core.get("ok", False):
        stability_score -= 0.6
    if resource_pressure > 0.9:
        stability_score -= 0.4
    elif resource_pressure > 0.75:
        stability_score -= 0.12
    if oscillation_risk:
        stability_score -= 0.2

    stability_score = round(max(0.0, stability_score), 4)
    stable = stability_score >= threshold and core.get("ok", False)

    actions.append({"prompt": prompt, "output": final_output, "stable": stable, "score": stability_score})
    history["actions"] = actions[-300:]
    hist_path.write_text(json.dumps(history, indent=2) + "\n", encoding="utf-8")

    out = {
        "ok": True,
        "stable": stable,
        "stability_score": stability_score,
        "threshold": threshold,
        "checks": {
            "core_integrity": bool(core.get("ok", False)),
            "resource_pressure": round(resource_pressure, 4),
            "oscillation_risk": oscillation_risk,
        },
    }
    (rt / "stability_enforcement.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    return out
