from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_MUTATING_STEP_KINDS = {
    "browser_action",
    "browser_open",
    "cloud_deploy",
    "github_issue_act",
    "github_issue_reply_post",
    "github_pr_act",
    "github_pr_reply_post",
    "recover",
    "self_repair",
    "store_install",
}
_VERIFICATION_STEP_KINDS = {
    "observe",
    "system_status",
    "browser_status",
    "browser_dom_inspect",
    "web_verify",
    "web_fetch",
    "store_status",
    "github_issue_read",
    "github_issue_comments",
    "github_issue_plan",
    "github_pr_read",
    "github_pr_comments",
    "github_pr_plan",
    "flow_monitor",
}


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


def _target_text(value: Any) -> str:
    if isinstance(value, dict):
        return " ".join(part for part in (_target_text(item) for item in value.values()) if part)
    if isinstance(value, (list, tuple, set)):
        return " ".join(part for part in (_target_text(item) for item in value) if part)
    return str(value or "").strip()


def analyze_goal_structure(request: str, decomposition: list[dict[str, Any]], targets: dict[str, Any]) -> dict[str, Any]:
    target_items = list(targets.get("items", []))
    target_types = sorted({str(item.get("type", "")) for item in target_items if str(item.get("type", ""))})
    action_hints = sorted(
        {
            str(action)
            for item in decomposition
            for action in list(item.get("action_hints", []))
            if str(action)
        }
    )
    blocking_count = sum(1 for item in decomposition if bool(item.get("blocking", False)))
    conditional_count = sum(1 for item in decomposition if bool(item.get("conditional", False)))
    failure_condition_count = sum(1 for item in decomposition if str(item.get("condition_type", "")) == "on_failure")
    dependency_count = sum(len(list(item.get("depends_on", []))) for item in decomposition)

    abstract_goal = "observe_state"
    if {"deploy"} & set(action_hints):
        abstract_goal = "configure_and_execute_deployment"
    elif {"reply", "post", "act"} & set(action_hints):
        abstract_goal = "coordinate_external_workflow"
    elif {"open", "click", "input"} & set(action_hints) and {"inspect", "show", "fetch"} & set(action_hints):
        abstract_goal = "inspect_then_mutate_resource"
    elif {"open", "click", "input"} & set(action_hints):
        abstract_goal = "mutate_resource"
    elif {"inspect", "show", "fetch", "status"} & set(action_hints):
        abstract_goal = "inspect_resource"

    request_shape = "single_step"
    if conditional_count:
        request_shape = "conditional_flow"
    elif dependency_count:
        request_shape = "dependency_chain"
    elif len(decomposition) > 2:
        request_shape = "multi_stage"
    elif len(target_types) > 1:
        request_shape = "mixed_target"

    return {
        "request": request,
        "abstract_goal": abstract_goal,
        "request_shape": request_shape,
        "action_hints": action_hints,
        "target_types": target_types,
        "target_count": len(target_items),
        "subgoal_count": len(decomposition),
        "dependency_count": dependency_count,
        "conditional_count": conditional_count,
        "failure_condition_count": failure_condition_count,
        "blocking_subgoal_count": blocking_count,
        "reasoning_notes": [
            note
            for note in [
                "conditional_structure_detected" if conditional_count else "",
                "failure_conditioned_fallback_detected" if failure_condition_count else "",
                "dependency_chain_detected" if dependency_count else "",
                "mixed_target_families_detected" if len(target_types) > 1 else "",
                "inspection_and_mutation_mixed" if {"open", "click", "input"} & set(action_hints) and {"inspect", "show", "fetch"} & set(action_hints) else "",
            ]
            if note
        ],
    }


def simulate_plan_conflicts(
    steps: list[dict[str, Any]],
    decomposition: list[dict[str, Any]],
    targets: dict[str, Any],
    *,
    read_only_request: bool = False,
) -> dict[str, Any]:
    step_kinds = [str(step.get("kind", "")) for step in steps]
    mutating_steps = [step for step in steps if str(step.get("kind", "")) in _MUTATING_STEP_KINDS]
    verification_steps = [step for step in steps if str(step.get("kind", "")) in _VERIFICATION_STEP_KINDS]
    target_types = sorted({str(item.get("type", "")) for item in list(targets.get("items", [])) if str(item.get("type", ""))})
    issues: list[dict[str, Any]] = []

    if read_only_request and mutating_steps:
        issues.append(
            {
                "code": "read_only_request_contains_mutation",
                "severity": "high",
                "message": "Read-only request still contains mutating steps before contradiction review.",
            }
        )
    if {"recover", "self_repair"} <= set(step_kinds):
        issues.append(
            {
                "code": "conflicting_remediation_paths",
                "severity": "high",
                "message": "Recovery and self-repair are both present in the same branch.",
            }
        )
    if len(target_types) > 1 and mutating_steps and not verification_steps:
        issues.append(
            {
                "code": "multi_target_mutation_without_verification",
                "severity": "medium",
                "message": "Plan mutates across mixed target families without a verification-first step.",
            }
        )
    browser_open_index = next((index for index, step in enumerate(steps) if str(step.get("kind", "")) == "browser_open"), None)
    browser_action_index = next((index for index, step in enumerate(steps) if str(step.get("kind", "")) == "browser_action"), None)
    if browser_open_index is not None and browser_action_index is not None and browser_action_index < browser_open_index:
        issues.append(
            {
                "code": "browser_action_before_open",
                "severity": "medium",
                "message": "Browser action appears before browser open in the candidate branch.",
            }
        )
    if any(bool(item.get("conditional", False)) for item in decomposition) and not any(str(step.get("kind", "")) in _VERIFICATION_STEP_KINDS for step in steps):
        issues.append(
            {
                "code": "conditional_flow_without_verification",
                "severity": "medium",
                "message": "Conditional flow has no verification step to anchor branch decisions.",
            }
        )
    for step in steps:
        requires = [str(item) for item in list(step.get("requires", [])) if str(item)]
        if requires and not any(required in step_kinds or required in list(step.get("decomposition_depends_on", [])) for required in requires):
            issues.append(
                {
                    "code": "missing_required_prerequisite",
                    "severity": "medium",
                    "message": f"Step `{step.get('kind', '')}` is missing at least one required prerequisite.",
                }
            )

    severity_weight = {"low": 0.04, "medium": 0.08, "high": 0.14}
    confidence_adjustment = round(sum(severity_weight.get(str(item.get("severity", "low")), 0.04) for item in issues), 3)
    return {
        "has_conflict": bool(issues),
        "issues": issues,
        "conflict_count": len(issues),
        "confidence_adjustment": min(0.28, confidence_adjustment),
        "recommended_mode": "safe" if any(item.get("severity") == "high" for item in issues) else "deliberate" if issues else "normal",
    }


def phase_plan(steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    phases = {
        "prepare": [],
        "execute": [],
        "fallback": [],
        "followup": [],
        "verify": [],
    }
    for index, step in enumerate(steps):
        kind = str(step.get("kind", ""))
        conditional_mode = str(step.get("conditional_execution_mode", "always"))
        if conditional_mode == "on_failure":
            phases["fallback"].append(index)
        elif conditional_mode in {"on_success", "on_verified"}:
            phases["followup"].append(index)
        elif kind in _VERIFICATION_STEP_KINDS or kind in {"cloud_target_set", "github_connect", "browser_open"}:
            phases["prepare"].append(index)
        elif kind in _MUTATING_STEP_KINDS:
            phases["execute"].append(index)
        else:
            phases["verify"].append(index)

    ordered: list[dict[str, Any]] = []
    for name in ("prepare", "execute", "fallback", "followup", "verify"):
        if not phases[name]:
            continue
        ordered.append(
            {
                "name": name,
                "step_indexes": list(phases[name]),
                "step_kinds": [str(steps[index].get("kind", "")) for index in phases[name]],
            }
        )
    return ordered


def derive_execution_mode(
    *,
    planner_confidence: float,
    risk_level: str,
    strategy: str,
    precheck: dict[str, Any] | None = None,
) -> str:
    precheck = dict(precheck or {})
    if str(strategy) == "conservative" or bool(precheck.get("has_conflict", False)):
        return "safe"
    if str(strategy) in {"dependency_aware", "verification_first"} or str(risk_level or "low").lower() in {"medium", "high"}:
        return "deliberate"
    if planner_confidence >= 0.92 and str(risk_level or "low").lower() == "low":
        return "fast"
    return "normal"


def explain_plan(
    *,
    intent_candidate: dict[str, Any],
    smart_profile: dict[str, Any],
    precheck: dict[str, Any],
    risk_level: str,
    branch_reason: str,
    simulation: dict[str, Any] | None = None,
    critique: dict[str, Any] | None = None,
    planner_confidence: float | None = None,
) -> dict[str, Any]:
    reasons = list(intent_candidate.get("reasons", []))
    precheck_codes = [str(item.get("code", "")) for item in list(precheck.get("issues", [])) if str(item.get("code", ""))]
    simulation = dict(simulation or {})
    critique = dict(critique or {})
    return {
        "intent_reason": " / ".join(reasons[:4]) if reasons else "weighted_intent_resolution",
        "branch_reason": branch_reason,
        "risk_reason": f"risk={risk_level}; strategy={smart_profile.get('strategy', 'direct_execute')}; conflicts={','.join(precheck_codes) if precheck_codes else 'none'}",
        "strategy_reason": ", ".join(list(smart_profile.get("reasons", []))[:4]) or "direct_execution_path",
        "confidence_reason": f"planner_confidence={round(float(planner_confidence or 0.0), 3)}; expected_success={simulation.get('expected_success', 0.0)}; critique={critique.get('summary', 'stable')}",
    }


def simulate_plan(
    steps: list[dict[str, Any]],
    decomposition: list[dict[str, Any]],
    targets: dict[str, Any],
    *,
    planner_confidence: float,
    risk_level: str,
    ambiguity_flags: list[str] | None = None,
    route_history_bias: dict[str, float] | None = None,
    precheck: dict[str, Any] | None = None,
    memory_strength: str = "none",
) -> dict[str, Any]:
    ambiguity_flags = list(ambiguity_flags or [])
    route_history_bias = dict(route_history_bias or {})
    precheck = dict(precheck or {})
    mutating_steps = [dict(step) for step in steps if str(step.get("risk_level", "low")) in {"medium", "high"}]
    verification_steps = [dict(step) for step in steps if str(step.get("verification_mode", "")) == "observe"]
    hard_dependencies = [
        dict(step)
        for step in steps
        if str(step.get("dependency_strength", "")) == "hard" or bool(dict(step.get("failure_impact") or {}).get("blocks"))
    ]

    expected_success = float(planner_confidence or 0.0)
    expected_success -= 0.12 if str(risk_level).lower() == "high" else 0.06 if str(risk_level).lower() == "medium" else 0.0
    expected_success -= min(0.18, len(ambiguity_flags) * 0.035)
    expected_success -= min(0.18, float(precheck.get("confidence_adjustment", 0.0) or 0.0))
    expected_success -= min(0.14, len(mutating_steps) * 0.035)
    expected_success -= min(0.08, len(hard_dependencies) * 0.02)
    expected_success += min(0.14, len(verification_steps) * 0.03)
    if memory_strength == "conflicting":
        expected_success -= 0.08
    elif memory_strength == "strong":
        expected_success += 0.03
    positive_bias = sum(max(0.0, float(value)) for value in route_history_bias.values())
    negative_bias = sum(abs(min(0.0, float(value))) for value in route_history_bias.values())
    expected_success += min(0.04, positive_bias * 0.2)
    expected_success -= min(0.06, negative_bias * 0.15)
    expected_success = round(max(0.05, min(0.99, expected_success)), 3)

    predicted_risk = "low"
    if str(risk_level).lower() == "high" or any(str(item.get("severity", "")) == "high" for item in list(precheck.get("issues", []))):
        predicted_risk = "high"
    elif str(risk_level).lower() == "medium" or len(mutating_steps) > 0 or len(ambiguity_flags) >= 2:
        predicted_risk = "medium"

    predicted_failure_points: list[dict[str, Any]] = []
    failure_propagation: dict[str, Any] = {}
    for step in steps:
        impact = dict(step.get("failure_impact") or {})
        step_key = str(step.get("kind", ""))
        failure_propagation[step_key] = {
            "requires": [str(item) for item in list(step.get("requires", [])) if str(item)],
            "enables": [str(item) for item in list(step.get("enables", [])) if str(item)],
            "breaks_if_failed": [str(item) for item in list(step.get("breaks_if_failed", [])) if str(item)],
            "uncertainty": float(step.get("uncertainty", 0.0) or 0.0),
        }
        if impact.get("blocks") or impact.get("degrades") or str(step.get("precondition_state", "")) in {"blocked", "degraded"}:
            predicted_failure_points.append(
                {
                    "kind": step_key,
                    "risk_level": str(step.get("risk_level", "low")),
                    "failure_impact": impact,
                    "precondition_state": str(step.get("precondition_state", "")),
                    "requires": [str(item) for item in list(step.get("requires", [])) if str(item)],
                    "enables": [str(item) for item in list(step.get("enables", [])) if str(item)],
                    "breaks_if_failed": [str(item) for item in list(step.get("breaks_if_failed", [])) if str(item)],
                    "uncertainty": round(float(step.get("uncertainty", 0.0) or 0.0), 3),
                }
            )

    return {
        "predicted_risk": predicted_risk,
        "expected_success": expected_success,
        "success_prob": expected_success,
        "mutation_count": len(mutating_steps),
        "verification_count": len(verification_steps),
        "hard_dependency_count": len(hard_dependencies),
        "target_count": len(list(targets.get("items", []))),
        "contradictions": [str(item.get("code", "")) for item in list(precheck.get("issues", [])) if str(item.get("code", ""))],
        "contradiction_risk": "high" if any(str(item.get("severity", "")) == "high" for item in list(precheck.get("issues", []))) else "medium" if bool(precheck.get("issues")) else "low",
        "failure_propagation": failure_propagation,
        "step_uncertainty_average": round(
            sum(float(step.get("uncertainty", 0.0) or 0.0) for step in steps) / max(1, len(steps)),
            3,
        ),
        "predicted_failure_points": predicted_failure_points[:8],
    }


def critique_plan(
    *,
    planner_confidence: float,
    coverage_ratio: float,
    simulation: dict[str, Any],
    precheck: dict[str, Any] | None = None,
    memory_strength: str = "none",
) -> dict[str, Any]:
    precheck = dict(precheck or {})
    simulation = dict(simulation or {})
    issues: list[dict[str, Any]] = []
    expected_success = float(simulation.get("expected_success", planner_confidence) or 0.0)
    predicted_risk = str(simulation.get("predicted_risk", "low"))

    if expected_success < 0.6:
        issues.append({"code": "low_expected_success", "severity": "high", "message": "Predicted success is too low for an unguarded primary plan."})
    if predicted_risk == "high" and int(simulation.get("verification_count", 0) or 0) == 0:
        issues.append({"code": "high_risk_without_verification", "severity": "high", "message": "High-risk plan lacks verification support."})
    if float(coverage_ratio or 0.0) < 1.0:
        issues.append({"code": "incomplete_target_coverage", "severity": "high", "message": "Explicit targets are not fully covered by the plan."})
    if bool(precheck.get("has_conflict", False)):
        issues.append({"code": "precheck_conflicts_present", "severity": "medium", "message": "Pre-execution conflict checks found plan friction."})
    if memory_strength == "conflicting":
        issues.append({"code": "conflicting_memory_support", "severity": "medium", "message": "Remembered context conflicts with the current request shape."})

    severity_rank = {"low": 0, "medium": 1, "high": 2}
    top_issue = max(issues, key=lambda item: severity_rank.get(str(item.get("severity", "low")), 0), default={})
    downgrade_recommended = any(str(item.get("severity", "")) == "high" for item in issues)
    recommended_mode = "safe" if downgrade_recommended else "deliberate" if expected_success < 0.75 else "normal"
    summary = str(top_issue.get("code", "stable")) if top_issue else "stable"
    return {
        "issue_count": len(issues),
        "issues": issues,
        "top_issue": summary,
        "downgrade_recommended": downgrade_recommended,
        "recommended_mode": recommended_mode,
        "summary": summary,
    }


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
    reasoning_trace: dict[str, Any] | None = None,
    precheck: dict[str, Any] | None = None,
    survivor_strategy_guidance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    ambiguity_flags = list(ambiguity_flags or [])
    route_history_bias = dict(route_history_bias or {})
    reasoning_trace = dict(reasoning_trace or {})
    precheck = dict(precheck or {})
    survivor_strategy_guidance = dict(survivor_strategy_guidance or {})
    target_items = list(targets.get("items", []))
    target_types = sorted({str(item.get("type", "")) for item in target_items if str(item.get("type", ""))})
    conditional_count = sum(1 for item in decomposition if bool(item.get("conditional", False)))
    failure_condition_count = sum(1 for item in decomposition if str(item.get("condition_type", "")) == "on_failure")
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
    complexity_score += min(0.08, failure_condition_count * 0.05)
    complexity_score += 0.08 if risk_level == "high" else 0.04 if risk_level == "medium" else 0.0
    complexity_score += min(0.08, len(ambiguity_flags) * 0.02)
    complexity_score += min(0.08, abs(max_negative_bias))
    complexity_score += min(0.08, float(precheck.get("confidence_adjustment", 0.0) or 0.0))
    complexity_score = round(max(0.0, min(1.0, complexity_score)), 3)

    if complexity_score >= 0.75:
        complexity = "high"
    elif complexity_score >= 0.45:
        complexity = "medium"
    else:
        complexity = "low"

    reasons: list[str] = []
    strategy = "direct_execute"
    if bool(precheck.get("has_conflict", False)) and float(precheck.get("confidence_adjustment", 0.0) or 0.0) >= 0.1:
        strategy = "conservative"
        reasons.append("precheck_conflicts_detected")
    elif planner_confidence < 0.55:
        strategy = "conservative"
        reasons.append("planner_confidence_low")
    elif str(survivor_strategy_guidance.get("preferred_strategy", "")).strip():
        strategy = str(survivor_strategy_guidance.get("preferred_strategy", "")).strip()
        reasons.append("survivor_strategy_guidance")
    elif max_negative_bias <= -0.08 and (mutating_count or complexity == "high"):
        strategy = "verification_first"
        reasons.append("route_history_penalizes_primary_path")
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
    if failure_condition_count:
        reasons.append("failure_conditioned_subgoals_present")
    if approval_possible_count:
        reasons.append("approval_possible_steps_present")
    if route_history_bias:
        reasons.append("route_history_bias_applied")
    if bool(survivor_strategy_guidance.get("outcome_guided", False)):
        reasons.append("strategy_outcome_guidance")
    if str(survivor_strategy_guidance.get("recovery_profile", "")).strip():
        reasons.append(f"recovery_profile:{str(survivor_strategy_guidance.get('recovery_profile', '')).strip()}")
    if reasoning_trace.get("abstract_goal"):
        reasons.append(f"abstract_goal:{reasoning_trace.get('abstract_goal')}")
    if len(target_items) > 1:
        reasons.append("multi_target_request")
    if complexity == "high":
        reasons.append("high_complexity_request")

    strategy_mode = "safe"
    if strategy == "conservative" or planner_confidence < 0.55:
        strategy_mode = "safe"
    elif complexity == "high" or len(target_items) > 2 or conditional_count:
        strategy_mode = "exploratory"
    elif planner_confidence >= 0.92 and str(risk_level or "low").lower() == "low" and len(target_items) <= 1:
        strategy_mode = "fast"
    elif planner_confidence >= 0.88 and mutating_count and str(risk_level or "low").lower() in {"low", "medium"}:
        strategy_mode = "aggressive"
    guidance_mode = str(survivor_strategy_guidance.get("preferred_mode", "")).strip()
    if guidance_mode and strategy != "conservative":
        strategy_mode = guidance_mode

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
    if list(survivor_strategy_guidance.get("preferred_branch_types", [])):
        recommended_branch_types.extend([str(item) for item in list(survivor_strategy_guidance.get("preferred_branch_types", [])) if str(item)])

    execution_mode = derive_execution_mode(
        planner_confidence=planner_confidence,
        risk_level=risk_level,
        strategy=strategy,
        precheck=precheck,
    )

    return {
        "request": request,
        "generated_utc": _utc_now(),
        "strategy": strategy,
        "strategy_mode": strategy_mode,
        "planner_mode": execution_mode,
        "complexity": complexity,
        "complexity_score": complexity_score,
        "planner_confidence": round(float(planner_confidence or 0.0), 3),
        "risk_level": str(risk_level or "low"),
        "subgoal_count": len(decomposition),
        "dependency_count": dependency_count,
        "conditional_count": conditional_count,
        "failure_condition_count": failure_condition_count,
        "blocking_subgoal_count": blocking_count,
        "target_count": len(target_items),
        "target_types": target_types,
        "mutating_step_count": mutating_count,
        "approval_possible_count": approval_possible_count,
        "ambiguity_flags": ambiguity_flags,
        "route_history_bias": {str(key): round(float(value), 3) for key, value in route_history_bias.items()},
        "recommended_branch_types": list(dict.fromkeys(recommended_branch_types)),
        "reasons": list(dict.fromkeys(reasons)),
        "survivor_strategy_guidance": survivor_strategy_guidance,
        "requires_dependency_tracking": bool(dependency_count or conditional_count),
        "requires_target_isolation": bool(len(target_items) > 1 and len(target_types) > 1),
        "conservative_mode_recommended": strategy == "conservative",
        "reasoning_trace": reasoning_trace,
        "precheck": precheck,
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
