from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _assistant_dir(cwd: str) -> Path:
    path = Path(cwd).resolve() / ".zero_os" / "assistant"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _smart_planner_path(cwd: str) -> Path:
    return _assistant_dir(cwd) / "smart_planner.json"


def _planner_feedback_path(cwd: str) -> Path:
    return _assistant_dir(cwd) / "planner_feedback.json"


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return default


def _save_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def derive_smart_planner_profile(
    request: str,
    steps: list[dict[str, Any]],
    decomposition: list[dict[str, Any]],
    targets: dict[str, Any],
    *,
    planner_confidence: float,
    risk_level: str,
    ambiguity_flags: list[str] | None = None,
    route_history_bias: dict[str, float] | None = None,
) -> dict[str, Any]:
    ambiguity_flags = list(ambiguity_flags or [])
    route_history_bias = dict(route_history_bias or {})
    target_items = list(targets.get("items", []))
    target_types = sorted({str(item.get("type", "")) for item in target_items if str(item.get("type", ""))})
    conditional_count = sum(1 for item in decomposition if bool(item.get("conditional", False)))
    dependency_count = sum(len(list(item.get("depends_on", []))) for item in decomposition)
    blocking_count = sum(1 for item in decomposition if bool(item.get("blocking", False)))
    mutating_count = sum(1 for step in steps if bool(step.get("mutation_requested_explicitly", False)))
    approval_possible_count = sum(1 for step in steps if bool(step.get("requires_approval_possible", False)))
    max_negative_bias = min([0.0] + [float(value) for value in route_history_bias.values()])
    complexity_score = 0.18
    complexity_score += min(0.22, max(0, len(decomposition) - 1) * 0.08)
    complexity_score += min(0.18, max(0, len(target_items) - 1) * 0.06)
    complexity_score += min(0.14, dependency_count * 0.05)
    complexity_score += min(0.1, conditional_count * 0.08)
    complexity_score += 0.08 if risk_level == "high" else 0.04 if risk_level == "medium" else 0.0
    complexity_score += min(0.08, len(ambiguity_flags) * 0.02)
    complexity_score += min(0.08, abs(max_negative_bias))
    complexity_score = round(max(0.0, min(1.0, complexity_score)), 3)

    if complexity_score >= 0.75:
        complexity = "high"
    elif complexity_score >= 0.45:
        complexity = "medium"
    else:
        complexity = "low"

    reasons: list[str] = []
    strategy = "direct_execute"
    if planner_confidence < 0.55:
        strategy = "conservative"
        reasons.append("planner_confidence_low")
    elif conditional_count or dependency_count:
        strategy = "dependency_aware"
        reasons.append("subgoal_dependencies_present")
    elif len(target_items) > 1 and len(target_types) > 1:
        strategy = "target_isolated"
        reasons.append("mixed_target_families")
    elif risk_level in {"high", "medium"} and mutating_count:
        strategy = "verification_first"
        reasons.append("mutating_or_risky_plan")

    if blocking_count:
        reasons.append("verification_blockers_present")
    if approval_possible_count:
        reasons.append("approval_possible_steps_present")
    if route_history_bias:
        reasons.append("route_history_bias_applied")
    if len(target_items) > 1:
        reasons.append("multi_target_request")
    if complexity == "high":
        reasons.append("high_complexity_request")

    recommended_branch_types = ["primary"]
    if strategy == "conservative":
        recommended_branch_types.extend(["minimal_safe", "observation_only", "conservative_execution"])
    elif strategy == "dependency_aware":
        recommended_branch_types.extend(["verification_first", "evidence_first"])
    elif strategy == "target_isolated":
        recommended_branch_types.extend(["verification_first", "single_target"])
    elif strategy == "verification_first":
        recommended_branch_types.extend(["verification_first", "evidence_first"])
    else:
        recommended_branch_types.extend(["verification_first"])

    return {
        "request": request,
        "generated_utc": _utc_now(),
        "strategy": strategy,
        "complexity": complexity,
        "complexity_score": complexity_score,
        "planner_confidence": round(float(planner_confidence or 0.0), 3),
        "risk_level": str(risk_level or "low"),
        "subgoal_count": len(decomposition),
        "dependency_count": dependency_count,
        "conditional_count": conditional_count,
        "blocking_subgoal_count": blocking_count,
        "target_count": len(target_items),
        "target_types": target_types,
        "mutating_step_count": mutating_count,
        "approval_possible_count": approval_possible_count,
        "ambiguity_flags": ambiguity_flags,
        "route_history_bias": {str(key): round(float(value), 3) for key, value in route_history_bias.items()},
        "recommended_branch_types": list(dict.fromkeys(recommended_branch_types)),
        "reasons": list(dict.fromkeys(reasons)),
        "requires_dependency_tracking": bool(dependency_count or conditional_count),
        "requires_target_isolation": bool(len(target_items) > 1 and len(target_types) > 1),
        "conservative_mode_recommended": strategy == "conservative",
    }


def record_smart_planner_snapshot(cwd: str, profile: dict[str, Any]) -> dict[str, Any]:
    payload = dict(profile)
    payload["path"] = str(_smart_planner_path(cwd))
    _save_json(_smart_planner_path(cwd), payload)
    return payload


def smart_planner_status(cwd: str) -> dict[str, Any]:
    latest = _load_json(_smart_planner_path(cwd), {})
    feedback = _load_json(_planner_feedback_path(cwd), {"summary": {"history_count": 0, "routes": {}}})
    summary = dict(feedback.get("summary") or {})
    routes = dict(summary.get("routes") or {})
    weakest_route = ""
    weakest_score = 1.0
    for route_name, metrics in routes.items():
        route_score = float(metrics.get("successful_completion_rate", 0.0) or 0.0) - float(metrics.get("contradiction_hold_rate", 0.0) or 0.0)
        if route_score < weakest_score:
            weakest_score = route_score
            weakest_route = str(route_name)
    return {
        "ok": True,
        "path": str(_smart_planner_path(cwd)),
        "planner_feedback_history_count": int(summary.get("history_count", 0) or 0),
        "weakest_route": weakest_route,
        "latest": latest,
    }
