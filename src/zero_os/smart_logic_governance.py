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


def _review_decisions_path(cwd: str) -> Path:
    return _runtime(cwd) / "false_positive_decisions.jsonl"


def _autonomy_history_path(cwd: str) -> Path:
    return Path(cwd).resolve() / ".zero_os" / "autonomy" / "history.json"


def _autonomy_history_stats(cwd: str, context: dict | None = None) -> dict:
    path = _autonomy_history_path(cwd)
    if not path.exists():
        return {"count": 0, "success_rate": 0.5, "quality_score": 0.5}
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {"count": 0, "success_rate": 0.5, "quality_score": 0.5}
    events = list(data.get("events", []))
    target_action = str((context or {}).get("action", "")).strip().lower()
    operation = str((context or {}).get("operation", "")).strip().lower()
    filtered = events
    if target_action:
        filtered = [item for item in events if str(item.get("action", "")).strip().lower() == target_action]
    elif operation:
        filtered = [item for item in events if operation in str(item.get("action", "")).strip().lower()]
    if not filtered:
        filtered = events[-20:]
    if not filtered:
        return {"count": 0, "success_rate": 0.5, "quality_score": 0.5}
    success = sum(1 for item in filtered if str(item.get("outcome", "")).lower() == "success")
    quality_values = [float(item.get("quality", 1.0 if str(item.get("outcome", "")).lower() == "success" else 0.0)) for item in filtered]
    return {
        "count": len(filtered),
        "success_rate": round(success / len(filtered), 4),
        "quality_score": round(sum(quality_values) / len(quality_values), 4),
    }


def _default_policy() -> dict:
    return {
        "global": {"review_enabled": True},
        "engines": {
            "zero_ai_gate_smart_logic_v1": {"min_confidence": 0.5},
            "zero_ai_internal_smart_logic_v1": {"min_confidence": 0.55},
            "cure_firewall_smart_logic_v1": {"min_confidence": 0.6},
            "antivirus_smart_logic_v1": {"min_confidence": 0.65},
            "zero_os_security_action_smart_logic_v1": {"min_confidence": 0.6},
            "zero_os_recovery_smart_logic_v1": {"min_confidence": 0.62},
            "zero_os_rollout_smart_logic_v1": {"min_confidence": 0.65},
            "zero_os_abuse_throttle_smart_logic_v1": {"min_confidence": 0.6},
            "zero_os_permission_trust_smart_logic_v1": {"min_confidence": 0.68},
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
    history = _autonomy_history_stats(cwd, context)
    out["autonomy_history"] = history
    confidence = float(out.get("confidence", 0.0))
    if history["count"] >= 3:
        blended = (float(history["success_rate"]) * 0.4) + (float(history["quality_score"]) * 0.6)
        history_bias = (blended - 0.5) * 0.14
        confidence = max(0.0, min(0.99, confidence + history_bias))
        out["confidence"] = round(confidence, 4)
        out["history_bias"] = round(history_bias, 4)
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


def list_false_positive_reviews(cwd: str, limit: int = 100) -> dict:
    path = _review_log_path(cwd)
    if not path.exists():
        return {"ok": True, "count": 0, "items": []}
    lines = [ln for ln in path.read_text(encoding="utf-8", errors="replace").splitlines() if ln.strip()]
    items = []
    for ln in lines[-max(1, min(500, int(limit))):]:
        try:
            items.append(json.loads(ln))
        except Exception:
            continue
    return {"ok": True, "count": len(items), "items": items}


def decide_false_positive(cwd: str, index: int, verdict: str, note: str = "") -> dict:
    verdict_norm = verdict.strip().lower()
    if verdict_norm not in {"confirmed", "false_positive"}:
        return {"ok": False, "reason": "verdict must be confirmed|false_positive"}
    reviews = list_false_positive_reviews(cwd, limit=10000).get("items", [])
    if index < 0 or index >= len(reviews):
        return {"ok": False, "reason": "index out of range"}
    rec = reviews[index]
    decision = {
        "time_utc": datetime.now(timezone.utc).isoformat(),
        "index": index,
        "verdict": verdict_norm,
        "note": note,
        "review": rec,
    }
    with _review_decisions_path(cwd).open("a", encoding="utf-8") as h:
        h.write(json.dumps(decision, sort_keys=True) + "\n")
    return {"ok": True, "decision": decision}
