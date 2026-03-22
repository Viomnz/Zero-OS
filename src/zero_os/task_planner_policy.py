from __future__ import annotations

from collections import defaultdict
from typing import Any

from zero_os.structured_intent import extract_intent
from zero_os.task_planner_parsing import MUTATION_TOKENS, READ_ONLY_TOKENS, _tokenize


_READ_ONLY_INTENTS = {"planning", "reasoning", "status", "tools"}
_HIGH_RISK_REMEDIATION_KINDS = {"recover", "self_repair"}
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
_READ_ONLY_STEP_KINDS = {
    "api_request",
    "api_workflow",
    "browser_dom_inspect",
    "browser_status",
    "capability_expansion_protocol",
    "contradiction_engine",
    "controller_registry",
    "flow_monitor",
    "general_agent",
    "github_connect",
    "github_issue_comments",
    "github_issue_plan",
    "github_issue_read",
    "github_pr_comments",
    "github_pr_plan",
    "github_pr_read",
    "highway_dispatch",
    "internet_capability",
    "maintenance_orchestrator",
    "observe",
    "pressure_harness",
    "smart_workspace",
    "store_status",
    "system_status",
    "tool_registry",
    "web_fetch",
    "web_verify",
    "world_class_readiness",
}
_VERIFICATION_PRIORITY_KINDS = _READ_ONLY_STEP_KINDS | {"autonomy_gate"}
_APPROVAL_POSSIBLE_KINDS = {"browser_action", "recover", "self_repair", "store_install"}
_INTENT_PRIORITY = {
    "feature_generation": 16,
    "capability_expansion_protocol": 15,
    "general_agent": 14,
    "reasoning": 13,
    "pressure": 12,
    "planning": 11,
    "flow_monitor": 10,
    "maintenance": 9,
    "workspace": 8,
    "world_class_readiness": 7,
    "internet": 6,
    "tools": 5,
    "browser": 4,
    "web": 3,
    "github": 3,
    "api": 3,
    "cloud": 3,
    "store_install": 3,
    "store_status": 3,
    "self_repair": 2,
    "recover": 2,
    "status": 1,
    "highway": 1,
    "observe": 0,
}
_INTENT_STEP_HINTS = {
    "planning": {"controller_registry"},
    "reasoning": {"contradiction_engine"},
    "pressure": {"pressure_harness"},
    "workspace": {"smart_workspace"},
    "maintenance": {"maintenance_orchestrator"},
    "world_class_readiness": {"world_class_readiness"},
    "internet": {"internet_capability"},
    "flow_monitor": {"flow_monitor"},
    "tools": {"tool_registry"},
    "web": {"web_verify", "web_fetch", "browser_open", "browser_action", "browser_dom_inspect"},
    "browser": {"browser_status", "browser_dom_inspect", "browser_action", "browser_open"},
    "status": {"system_status", "observe"},
    "store_status": {"store_status"},
    "store_install": {"store_install"},
    "self_repair": {"self_repair", "autonomy_gate"},
    "recover": {"recover", "autonomy_gate"},
    "api": {"api_request", "api_workflow"},
    "github": {
        "github_connect",
        "github_issue_read",
        "github_issue_comments",
        "github_issue_plan",
        "github_issue_act",
        "github_issue_reply_draft",
        "github_issue_reply_post",
        "github_pr_read",
        "github_pr_comments",
        "github_pr_plan",
        "github_pr_act",
        "github_pr_reply_draft",
        "github_pr_reply_post",
    },
    "cloud": {"cloud_target_set", "cloud_deploy"},
    "general_agent": {"general_agent"},
    "capability_expansion_protocol": {"capability_expansion_protocol"},
    "feature_generation": {"domain_pack_generate_feature"},
    "highway": {"highway_dispatch"},
}
_EXCLUSIVE_PATTERNS = (
    (
        "planning",
        lambda lowered: lowered.strip() in {"highest value steps", "highest-value steps"}
        or any(token in lowered for token in ("highest value", "highest-value", "next step", "next steps", "what should improve")),
    ),
    ("capability_expansion_protocol", lambda lowered: "zero ai capability expansion protocol status" in lowered),
    ("general_agent", lambda lowered: "make zero ai can do agentic general-purpose ai" in lowered or "general-purpose ai" in lowered),
    ("reasoning", lambda lowered: "contradiction status" in lowered),
    ("pressure", lambda lowered: "pressure harness" in lowered or "zero ai pressure run" in lowered),
    ("feature_generation", lambda lowered: lowered.startswith("add feature ")),
)


def _target_signal_strength(intent_name: str, targets: dict[str, Any]) -> float:
    coverage = {
        "web": float(len(list(targets.get("urls", []))) > 0),
        "browser": float(len(list(targets.get("urls", []))) > 0),
        "github": float(
            any(
                targets.get(key)
                for key in (
                    "repos",
                    "issue_reads",
                    "issue_comments",
                    "issue_plans",
                    "issue_actions",
                    "issue_reply_drafts",
                    "issue_reply_posts",
                    "pr_reads",
                    "pr_comments",
                    "pr_plans",
                    "pr_actions",
                    "pr_reply_drafts",
                    "pr_reply_posts",
                )
            )
        ),
        "api": float(any(targets.get(key) for key in ("api_requests", "api_workflows"))),
        "cloud": float(any(targets.get(key) for key in ("cloud_targets", "deployments"))),
        "store_install": float(len(list(targets.get("apps", []))) > 0),
        "highway": float(any(targets.get(key) for key in ("commands", "files"))),
    }
    return float(coverage.get(intent_name, 1.0))


def _plan_risk_level(steps: list[dict[str, Any]]) -> str:
    levels = {str(step.get("risk_level", "low")) for step in steps}
    if "high" in levels:
        return "high"
    if "medium" in levels:
        return "medium"
    return "low"


def _step_covers_target(step: dict[str, Any], item: dict[str, Any]) -> bool:
    target_id = str(item.get("id", ""))
    if target_id and target_id in list(step.get("attached_targets", [])):
        return True

    kind = str(step.get("kind", ""))
    target = step.get("target")
    target_type = str(item.get("type", ""))
    target_value = item.get("value")

    if target_type == "actions":
        action = str(target_value or "").strip().lower()
        if action == "open":
            return kind == "browser_open"
        if action in {"click", "submit"}:
            return kind == "browser_action" and str(dict(target or {}).get("action", "")).strip().lower() == action
        if action in {"type", "input"}:
            return kind == "browser_action" and str(dict(target or {}).get("action", "")).strip().lower() == "input"
        if action in {"read", "show"}:
            return kind in {"highway_dispatch", "web_fetch", "browser_status", "system_status", "store_status"}
        if action == "inspect":
            return kind in {"browser_dom_inspect", "web_verify", "flow_monitor"}
        if action == "fetch":
            return kind in {"web_fetch", "api_request", "api_workflow"}
        if action == "status":
            return kind in {"browser_status", "system_status", "store_status", "internet_capability", "world_class_readiness"}
        if action == "install":
            return kind == "store_install"
        if action == "deploy":
            return kind == "cloud_deploy"
        if action == "recover":
            return kind == "recover"
        if action == "repair":
            return kind == "self_repair"
        if action == "reply":
            return kind in {"github_issue_reply_draft", "github_issue_reply_post", "github_pr_reply_draft", "github_pr_reply_post"}
        if action == "act":
            return kind in {"github_issue_act", "github_pr_act"}
        if action == "plan":
            return kind in {"github_issue_plan", "github_pr_plan", "controller_registry"}
        return False

    if target_type == "files":
        file_value = str(target_value or "").strip()
        if not file_value:
            return False
        target_text = str(target or "")
        return kind == "highway_dispatch" and file_value in target_text

    if target_type == "commands":
        return kind == "highway_dispatch" and str(target or "").strip() == str(target_value or "").strip()

    return False


def _annotate_step_contracts(steps: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    annotated: list[dict[str, Any]] = []
    plan_flags: list[str] = []
    for step in steps:
        updated = dict(step)
        issues: list[str] = []
        preconditions: list[str] = []
        confidence = float(updated.get("route_confidence", 0.0) or 0.0)
        kind = str(updated.get("kind", ""))
        target = updated.get("target")

        if kind == "browser_open":
            preconditions.extend(["url_required", "browser_session_available"])
            if not str(target or "").strip():
                issues.append("browser_open_missing_url")
                confidence -= 0.35
        elif kind == "browser_action":
            browser_target = dict(target or {})
            preconditions.extend(["url_required", "action_required", "selector_or_default_policy"])
            if not str(browser_target.get("url", "")).strip():
                issues.append("browser_action_missing_url")
                confidence -= 0.35
            if not str(browser_target.get("action", "")).strip():
                issues.append("browser_action_missing_action")
                confidence -= 0.25
            selector = str(browser_target.get("selector", "")).strip()
            if not selector:
                issues.append("browser_action_missing_selector")
                confidence -= 0.2
            elif selector == "body" and str(browser_target.get("action", "")).strip() == "click":
                issues.append("generic_browser_selector")
                confidence -= 0.12
            if str(browser_target.get("action", "")).strip() == "input" and not str(browser_target.get("value", "")).strip():
                issues.append("browser_action_missing_value")
                confidence -= 0.35
        elif kind in {"github_issue_reply_post", "github_pr_reply_post"}:
            preconditions.extend(["repo_required", "object_id_required", "reply_text_required"])
            target_map = dict(target or {})
            if not str(target_map.get("repo", "")).strip():
                issues.append("github_reply_missing_repo")
                confidence -= 0.25
            if not str(target_map.get("text", "")).strip():
                issues.append("github_reply_missing_text")
                confidence -= 0.35
        elif kind in {"github_issue_act", "github_pr_act"}:
            preconditions.extend(["repo_required", "object_id_required"])
            target_map = dict(target or {})
            if not str(target_map.get("repo", "")).strip():
                issues.append("github_action_missing_repo")
                confidence -= 0.25
        elif kind == "cloud_deploy":
            preconditions.extend(["artifact_required", "target_required"])
            target_map = dict(target or {})
            if not str(target_map.get("artifact", "")).strip():
                issues.append("deploy_missing_artifact")
                confidence -= 0.3
            if not str(target_map.get("target", "")).strip():
                issues.append("deploy_missing_target")
                confidence -= 0.3
        elif kind == "api_request":
            preconditions.extend(["profile_required", "path_required"])
            target_map = dict(target or {})
            if not str(target_map.get("profile", "")).strip():
                issues.append("api_request_missing_profile")
                confidence -= 0.25
            if not str(target_map.get("path", "")).strip():
                issues.append("api_request_missing_path")
                confidence -= 0.25
        elif kind == "api_workflow":
            preconditions.extend(["profile_required", "workflow_paths_required"])
            target_map = dict(target or {})
            if not str(target_map.get("profile", "")).strip():
                issues.append("api_workflow_missing_profile")
                confidence -= 0.25
            if not list(target_map.get("paths", [])):
                issues.append("api_workflow_missing_paths")
                confidence -= 0.25
        elif kind in {"recover", "self_repair"}:
            preconditions.extend(["runtime_scope_required", "rollback_path_preferred"])

        updated["preconditions"] = preconditions
        updated["precondition_issues"] = issues
        updated["precondition_state"] = "blocked" if confidence <= 0.2 else "degraded" if issues else "ready"
        updated["route_confidence"] = round(max(0.0, min(1.0, confidence)), 3)
        updated["confidence"] = updated["route_confidence"]
        annotated.append(updated)
        for issue in issues:
            if issue not in plan_flags:
                plan_flags.append(issue)
    return annotated, plan_flags


def _memory_context_summary(memory_context: dict, *, mode: str = "balanced") -> dict:
    filtered = dict(memory_context.get("filtered_out", {}))
    filtered_total = int(filtered.get("task_memory", 0) or 0) + int(filtered.get("playbook", 0) or 0)
    memory_confidence = float(memory_context.get("memory_confidence", 0.0) or 0.0)
    if mode == "disabled":
        memory_strength = "none"
    elif filtered_total and memory_confidence < 0.6:
        memory_strength = "conflicting"
    elif memory_confidence >= 0.7:
        memory_strength = "strong"
    elif memory_confidence > 0.0:
        memory_strength = "weak"
    else:
        memory_strength = "none"
    return {
        "intent": memory_context.get("intent", "observe"),
        "memory_confidence": memory_confidence,
        "memory_strength": memory_strength,
        "memory_mode": mode,
        "same_system": memory_context.get("same_system", False),
        "contradiction_free": memory_context.get("contradiction_free", False),
        "support_by_kind": dict(memory_context.get("support_by_kind", {})),
        "core_constraints": list(memory_context.get("core_constraints", [])),
        "core_goals": list(memory_context.get("core_goals", [])),
        "items": list(memory_context.get("items", [])),
        "filtered_out": filtered,
    }


def _coverage_for_steps(targets: dict[str, Any], steps: list[dict[str, Any]]) -> dict[str, Any]:
    coverage_map: dict[str, list[int]] = {}
    target_items = list(targets.get("items", []))
    for index, step in enumerate(steps):
        for item in target_items:
            target_id = str(item.get("id", ""))
            if not target_id:
                continue
            if _step_covers_target(step, item):
                coverage_map.setdefault(target_id, []).append(index)
    target_ids = [str(item.get("id", "")) for item in target_items if str(item.get("id", ""))]
    unbound_target_ids = [target_id for target_id in target_ids if target_id not in coverage_map]
    return {
        "coverage_map": coverage_map,
        "covered_target_ids": sorted(coverage_map),
        "covered_targets": [item for item in target_items if str(item.get("id", "")) in coverage_map],
        "unbound_target_ids": unbound_target_ids,
        "unbound_targets": [item for item in target_items if str(item.get("id", "")) in unbound_target_ids],
        "coverage_ratio": 1.0 if not target_ids else round((len(target_ids) - len(unbound_target_ids)) / len(target_ids), 3),
    }


def _planner_confidence(intent_confidence: float, coverage_ratio: float, ambiguity_count: int, conflict_count: int, dropped_count: int) -> float:
    ambiguity_penalty = min(0.35, ambiguity_count * 0.08)
    conflict_penalty = min(0.25, conflict_count * 0.06)
    dropped_penalty = min(0.2, dropped_count * 0.06)
    confidence = (intent_confidence * 0.55) + (coverage_ratio * 0.3) + ((1.0 - ambiguity_penalty - conflict_penalty - dropped_penalty) * 0.15)
    return round(max(0.0, min(1.0, confidence)), 3)


def _strip_memory_context(memory_context: dict) -> dict:
    items = [dict(item) for item in list(memory_context.get("items", [])) if str(item.get("tier", "")) in {"tier1_current", "tier4_core"}]
    return {
        "ok": True,
        "request": memory_context.get("request", ""),
        "intent": memory_context.get("intent", "observe"),
        "items": items,
        "filtered_out": dict(memory_context.get("filtered_out", {})),
        "support_by_kind": {},
        "memory_confidence": 0.0,
        "core_constraints": list(memory_context.get("core_constraints", [])),
        "core_goals": list(memory_context.get("core_goals", [])),
        "same_system": bool(memory_context.get("same_system", False)),
        "contradiction_free": bool(memory_context.get("contradiction_free", False)),
    }


def _memory_bias_for_intent(intent_name: str, memory_context: dict[str, Any], mode: str) -> float:
    if mode == "disabled":
        return 0.0
    support_by_kind = dict(memory_context.get("support_by_kind", {}))
    support = [float(support_by_kind.get(kind, 0.0)) for kind in _INTENT_STEP_HINTS.get(intent_name, set())]
    if not support:
        return 0.0
    filtered = dict(memory_context.get("filtered_out", {}))
    filtered_total = int(filtered.get("task_memory", 0) or 0) + int(filtered.get("playbook", 0) or 0)
    memory_confidence = float(memory_context.get("memory_confidence", 0.0) or 0.0)
    stale_penalty = 0.15 if filtered_total and memory_confidence < 0.5 else 0.0
    scale = 0.35 if mode == "supported" else 0.18
    return round(max(0.0, (sum(support) / len(support)) * scale - stale_penalty), 3)


def _resolve_intents(
    request: str,
    targets: dict[str, Any],
    memory_context: dict[str, Any],
    *,
    memory_mode: str,
    route_history_bias: dict[str, float] | None = None,
) -> dict[str, Any]:
    text = request.strip()
    lowered = text.lower()
    structured = extract_intent(text)
    scores: defaultdict[str, float] = defaultdict(float)
    reasons: defaultdict[str, list[str]] = defaultdict(list)

    def bump(intent_name: str, weight: float, reason: str) -> None:
        scores[intent_name] += weight
        reasons[intent_name].append(reason)

    if structured.get("intent", "observe") != "observe":
        bump(str(structured.get("intent")), 0.8, "structured_intent")
    for intent_name, matcher in _EXCLUSIVE_PATTERNS:
        if matcher(lowered):
            bump(intent_name, 2.0, "exclusive_match")
    if targets.get("urls"):
        bump("web", 1.2, "explicit_url")
        if any(token in lowered for token in ("open", "click", "submit", "type", "inspect page", "browser status")):
            bump("browser", 0.8, "browser_tokens_with_url")
        if any(token in lowered for token in ("open", "click", "submit", "type", "input")):
            bump("web", 0.7, "explicit_web_mutation_with_url")
            bump("browser", 0.5, "explicit_browser_mutation")
    if "browser status" in lowered or any(token in lowered for token in ("browser tabs", "browser session")):
        bump("web", 1.3, "browser_status_phrase")
        bump("browser", 1.05, "browser_status_phrase")
    elif any(token in lowered for token in ("browser", "open", "click", "submit", "type", "input")):
        bump("browser", 0.55, "browser_phrase_without_target")
        bump("web", 0.45, "web_phrase_without_target")
    if any(token in lowered for token in ("tools", "capabilities", "what can you do")):
        bump("tools", 1.0, "tools_phrase")
    if any(token in lowered for token in ("status", "diagnostic", "health", "check")) and not targets.get("urls") and "browser status" not in lowered:
        bump("status", 0.8, "status_phrase")
    if "smart workspace" in lowered:
        bump("workspace", 1.1, "workspace_phrase")
    if "maintenance" in lowered and "domain pack" not in lowered:
        bump("maintenance", 1.1, "maintenance_phrase")
    if "world class" in lowered and "readiness" in lowered:
        bump("world_class_readiness", 1.2, "readiness_phrase")
    if "internet" in lowered and not targets.get("urls") and "browser" not in lowered:
        bump("internet", 1.0, "internet_phrase")
    if any(token in lowered for token in ("find contradiction", "bugs", "errors", "virus", "flow monitor", "flow scan", "malware")):
        bump("flow_monitor", 1.1, "flow_phrase")
    if targets.get("apps"):
        bump("store_install", 1.0, "install_app_target")
    if "native store status" in lowered or "store status" in lowered:
        bump("store_status", 1.0, "store_status_phrase")
    if "self repair" in lowered:
        bump("self_repair", 1.4, "explicit_self_repair")
    if "recover" in lowered or "recovery" in lowered:
        bump("recover", 1.4, "explicit_recover")
    if targets.get("api_requests") or targets.get("api_workflows"):
        bump("api", 1.0, "api_target")
    github_target_keys = {
        "repos",
        "issue_reads",
        "issue_comments",
        "issue_plans",
        "issue_actions",
        "issue_reply_drafts",
        "issue_reply_posts",
        "pr_reads",
        "pr_comments",
        "pr_plans",
        "pr_actions",
        "pr_reply_drafts",
        "pr_reply_posts",
    }
    if any(targets.get(key) for key in github_target_keys):
        bump("github", 1.0, "github_target")
    elif "github" in lowered:
        bump("github", 0.55, "github_phrase_without_target")
    if targets.get("cloud_targets") or targets.get("deployments"):
        bump("cloud", 1.0, "cloud_target")
    elif "cloud" in lowered or "deploy" in lowered:
        bump("cloud", 0.55, "cloud_phrase_without_target")
    if targets.get("feature_requests"):
        bump("feature_generation", 1.2, "feature_request")
    if targets.get("commands"):
        bump("highway", 0.9, "command_target")
    for intent_name in list(_INTENT_PRIORITY):
        bias = _memory_bias_for_intent(intent_name, memory_context, memory_mode)
        if bias:
            bump(intent_name, bias, f"memory_bias:{memory_mode}")
    for intent_name, bias in dict(route_history_bias or {}).items():
        if abs(float(bias or 0.0)) >= 0.01:
            bump(str(intent_name), float(bias), "route_history_bias")
    if not scores:
        bump("observe", 1.0, "fallback")
    ordered = sorted(scores.items(), key=lambda item: (item[1], _INTENT_PRIORITY.get(item[0], 0), item[0]), reverse=True)
    top_score = ordered[0][1] if ordered else 1.0
    candidates = [
        {
            "intent": intent_name,
            "score": round(score, 3),
            "confidence": round(min(1.0, score / max(top_score, 0.001)), 3),
            "reasons": list(reasons.get(intent_name, [])),
        }
        for intent_name, score in ordered
    ]
    primary = candidates[0] if candidates else {"intent": "observe", "confidence": 1.0, "score": 1.0}
    secondary = [candidate["intent"] for candidate in candidates[1:] if candidate["score"] >= max(0.65, primary["score"] * 0.6)]
    ambiguity_flags: list[str] = []
    if len(candidates) > 1 and abs(candidates[0]["score"] - candidates[1]["score"]) <= 0.2:
        ambiguity_flags.append("competing_primary_intents")
        ambiguity_flags.append("multi_intent")
    if len([candidate for candidate in candidates if candidate["score"] >= max(0.6, primary["score"] * 0.55)]) > 1:
        ambiguity_flags.append("mixed_intents")
    if {"recover", "self_repair"} <= {candidate["intent"] for candidate in candidates[:3]}:
        ambiguity_flags.append("conflicting_remediation_intents")
    if bool(_tokenize(lowered) & READ_ONLY_TOKENS) and bool(_tokenize(lowered) & MUTATION_TOKENS):
        ambiguity_flags.append("read_only_mutation_overlap")
    if "tools" in lowered and bool(_tokenize(lowered) & MUTATION_TOKENS):
        ambiguity_flags.append("tools_execute_overlap")
    if "status" in lowered and any(token in lowered for token in ("open", "click", "submit", "input", "type")):
        ambiguity_flags.append("status_execution_overlap")
    if _target_signal_strength(primary["intent"], targets) < 1.0:
        ambiguity_flags.append("low_target_signal")
    conflicting_signals: list[str] = []
    if {"recover", "self_repair"} <= {candidate["intent"] for candidate in candidates[:4]}:
        conflicting_signals.append("recover_and_self_repair_overlap")
    if "read_only_mutation_overlap" in ambiguity_flags:
        conflicting_signals.append("read_only_mutation_overlap")
    if "tools_execute_overlap" in ambiguity_flags:
        conflicting_signals.append("tools_execute_overlap")
    if "status_execution_overlap" in ambiguity_flags:
        conflicting_signals.append("status_execution_overlap")
    return {
        "structured_intent": structured,
        "primary_intent": primary["intent"],
        "primary_confidence": primary["confidence"],
        "candidates": candidates,
        "intent_scores": {candidate["intent"]: candidate["score"] for candidate in candidates},
        "secondary_intents": secondary,
        "ambiguity_flags": list(dict.fromkeys(ambiguity_flags)),
        "conflicting_signals": conflicting_signals,
        "route_history_bias": {str(key): round(float(value), 3) for key, value in dict(route_history_bias or {}).items()},
    }
