from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


def _runtime(cwd: str) -> Path:
    p = Path(cwd).resolve() / ".zero_os" / "runtime"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _policy_path(cwd: str) -> Path:
    return _runtime(cwd) / "smart_logic_policy.json"


def _review_log_path(cwd: str) -> Path:
    return _runtime(cwd) / "false_positive_review.jsonl"


def _default_policy() -> dict:
    return {
        "global": {"review_enabled": True},
        "engines": {
            "zero_ai_gate_smart_logic_v1": {"min_confidence": 0.5},
            "zero_ai_internal_smart_logic_v1": {"min_confidence": 0.55},
            "cure_firewall_smart_logic_v1": {"min_confidence": 0.6},
            "antivirus_smart_logic_v1": {"min_confidence": 0.65},
        },
    }


def load_engine_policy(cwd: str, engine: str) -> dict:
    p = _policy_path(cwd)
    default = _default_policy()
    if not p.exists():
        p.write_text(json.dumps(default, indent=2) + "\n", encoding="utf-8")
        return {"review_enabled": True, "min_confidence": float(default["engines"].get(engine, {}).get("min_confidence", 0.6))}
    try:
        data = json.loads(p.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        data = default
    review_enabled = bool((data.get("global", {}) or {}).get("review_enabled", True))
    min_conf = float(((data.get("engines", {}) or {}).get(engine, {}) or {}).get("min_confidence", 0.6))
    return {"review_enabled": review_enabled, "min_confidence": min_conf}


def apply_governance(cwd: str, logic: dict, context: dict | None = None) -> dict:
    out = dict(logic or {})
    engine = str(out.get("engine", "unknown"))
    policy = load_engine_policy(cwd, engine)
    out["governance_policy"] = policy
    confidence = float(out.get("confidence", 0.0))
    action = str(out.get("decision_action", ""))
    if action in {"execute", "allow", "allow_with_monitoring", "allow_and_mark_beacon"} and confidence < float(policy["min_confidence"]):
        out["decision_action"] = "hold_for_review"
        out["decision_reason"] = "below_confidence_threshold"
        out.setdefault("root_issues", {"failed_checks": [], "issue_sources": []})
        out["root_issues"].setdefault("issue_sources", [])
        out["root_issues"]["issue_sources"].append("below_confidence_threshold")
    should_review = bool(policy["review_enabled"]) and str(out.get("decision_action", "")).lower() in {
        "reject_and_regenerate",
        "reject_or_hold",
        "block",
        "block_and_repair",
        "quarantine_now",
        "manual_containment",
        "hold_for_review",
    }
    out["false_positive_review_needed"] = should_review
    if should_review:
        rec = {
            "time_utc": datetime.now(timezone.utc).isoformat(),
            "engine": engine,
            "decision_action": out.get("decision_action", ""),
            "decision_reason": out.get("decision_reason", ""),
            "confidence": confidence,
            "context": context or {},
            "root_issues": out.get("root_issues", {}),
        }
        with _review_log_path(cwd).open("a", encoding="utf-8") as h:
            h.write(json.dumps(rec, sort_keys=True) + "\n")
    return out

