from __future__ import annotations

import json
import re
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from zero_os.code_task_lane import parse_code_instruction
from zero_os.code_workbench import code_workbench_status, overlay_world_model_with_codebase
from zero_os.decision_governor import governor_decide
from zero_os.memory_tier_filter import build_memory_context, score_branch_support
from zero_os.playbook_memory import lookup
from zero_os.semantic_reasoner import generate_semantic_interpretations, semantic_abstraction_profile
from zero_os.self_derivation_engine import (
    derive_interpretations,
    pattern_guided_steps,
    self_derivation_revalidate as _self_derivation_revalidate,
    self_derivation_status as _self_derivation_status,
    survivor_generation_guidance,
    survivor_history_score,
    survivor_strategy_guidance,
)
from zero_os.smart_planner import (
    analyze_goal_structure,
    critique_plan,
    derive_smart_planner_profile,
    explain_plan,
    phase_plan,
    record_smart_planner_snapshot,
    simulate_plan,
    simulate_plan_conflicts,
    smart_planner_status as _smart_planner_status,
)
from zero_os.structured_intent import extract_intent
from zero_os.task_planner_composer import compose_primary_steps, make_step, step_allows_mutation
from zero_os.task_planner_parsing import _normalize_text, _request_is_read_only, _split_subgoals, extract_request_targets
from zero_os.task_planner_policy import (
    MUTATION_TOKENS,
    _HIGH_RISK_REMEDIATION_KINDS,
    _READ_ONLY_STEP_KINDS,
    _VERIFICATION_PRIORITY_KINDS,
    _annotate_step_contracts,
    _coverage_for_steps,
    _memory_context_summary,
    _plan_risk_level,
    _planner_confidence,
    _resolve_intents,
    _strip_memory_context,
)
from zero_os.world_model import world_model_status


PLANNER_VERSION = "2026.03.22"
PLANNER_FEEDBACK_SCHEMA_VERSION = 3


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _planner_world_model_context(cwd: str) -> dict[str, Any]:
    model = dict(world_model_status(cwd) or {})
    domains = dict(model.get("domains") or {})
    runtime = dict((domains.get("runtime") or {}).get("summary") or {})
    continuity = dict((domains.get("continuity") or {}).get("summary") or {})
    approvals = dict((domains.get("approvals") or {}).get("summary") or {})
    jobs = dict((domains.get("jobs") or {}).get("summary") or {})
    pressure = dict((domains.get("pressure") or {}).get("summary") or {})
    codebase = dict((domains.get("codebase") or {}).get("summary") or {})
    goals = dict((domains.get("goals") or {}).get("summary") or {})
    observation_stream = dict((domains.get("observation_stream") or {}).get("summary") or {})
    causal = dict(model.get("causal_assessment") or {})
    return {
        "available": bool(model.get("ok", False)) and not bool(model.get("missing", False)),
        "missing": bool(model.get("missing", False)),
        "time_utc": str(model.get("time_utc", "")),
        "fact_count": int(model.get("fact_count", 0) or 0),
        "blocked_domains": list(model.get("blocked_domains", [])),
        "degraded_domains": list(model.get("degraded_domains", [])),
        "runtime_ready": bool(runtime.get("runtime_ready", False)),
        "runtime_missing": bool(runtime.get("runtime_missing", False)),
        "continuity_healthy": bool(continuity.get("same_system", False)) and not bool(continuity.get("has_contradiction", False)),
        "approvals_pending": int(approvals.get("pending_count", 0) or 0),
        "jobs_pending": int(jobs.get("pending_count", 0) or 0),
        "pressure_ready": bool(pressure.get("pressure_ready", False)),
        "codebase_scope_ready": bool(codebase.get("scope_ready", True)),
        "codebase_verification_ready": bool(codebase.get("verification_ready", True)),
        "goal_count": int(goals.get("goal_count", 0) or 0),
        "open_goal_count": int(goals.get("open_count", 0) or 0),
        "blocked_goal_count": int(goals.get("blocked_count", 0) or 0),
        "current_goal_title": str(goals.get("current_goal_title", "") or ""),
        "current_goal_next_action": str(goals.get("current_goal_next_action", "") or ""),
        "observation_blocking_event_count": int(observation_stream.get("blocking_event_count", 0) or 0),
        "causal_action_bias": str(causal.get("action_bias", "observe") or "observe"),
        "predicted_failure_modes": list(causal.get("predicted_failure_modes", [])),
    }


def _goal_alignment_score(request_text: str, plan: dict[str, Any], world_model_context: dict[str, Any]) -> dict[str, Any]:
    current_goal_title = str(world_model_context.get("current_goal_title", "") or "").strip()
    current_goal_next_action = str(world_model_context.get("current_goal_next_action", "") or "").strip()
    action_bias = str(world_model_context.get("causal_action_bias", "observe") or "observe").strip().lower()
    if not current_goal_title and not current_goal_next_action and action_bias == "observe":
        return {
            "score": 0.0,
            "current_goal_title": "",
            "current_goal_next_action": "",
            "action_bias": action_bias,
            "matched_request_terms": [],
            "matched_step_terms": [],
        }

    request_lower = _normalize_text(request_text).lower()
    steps = [dict(step) for step in list(plan.get("steps", []))]
    step_text = " ".join(
        " ".join(
            [
                str(step.get("kind", "")),
                json.dumps(step.get("target", ""), sort_keys=True, default=str),
                " ".join(str(item) for item in list(step.get("attached_targets", []))),
            ]
        )
        for step in steps
    ).lower()
    branch_id = str((plan.get("branch") or {}).get("id", "") or "").strip().lower()
    token_source = f"{current_goal_title} {current_goal_next_action}".lower()
    tokens = [
        token
        for token in re.split(r"[^a-z0-9]+", token_source)
        if len(token) >= 4 and token not in {"https", "http", "www", "json", "true", "false"}
    ]
    unique_tokens = list(dict.fromkeys(tokens))
    matched_request_terms = [token for token in unique_tokens if token in request_lower]
    matched_step_terms = [token for token in unique_tokens if token in step_text]

    score = min(0.12, len(matched_request_terms) * 0.02) + min(0.18, len(matched_step_terms) * 0.04)
    allows_mutation = any(step_allows_mutation(str(step.get("kind", ""))) for step in steps)
    coverage_ratio = float(dict(plan.get("target_coverage") or {}).get("coverage_ratio", 0.0) or 0.0)

    if action_bias == "goal_progress":
        if allows_mutation and coverage_ratio >= 1.0:
            score += 0.06
        elif branch_id in {"observation_only", "minimal_safe", "conservative_execution"}:
            score -= 0.04
    elif action_bias == "wait_for_user":
        score += 0.03 if not allows_mutation else -0.06
    elif action_bias == "run_runtime":
        if any(str(step.get("kind", "")) in {"run_runtime", "autonomy_gate"} for step in steps):
            score += 0.08
    elif action_bias == "repair_continuity":
        if any("continuity" in json.dumps(step.get("target", ""), sort_keys=True, default=str).lower() for step in steps):
            score += 0.08
    elif action_bias == "stabilize_recovery":
        if any(str(step.get("kind", "")) == "recover" or "recovery" in json.dumps(step.get("target", ""), sort_keys=True, default=str).lower() for step in steps):
            score += 0.08
    elif action_bias == "wait_for_clean_scope":
        if any(str(step.get("kind", "")) == "code_change" for step in steps):
            score -= 0.08
        else:
            score += 0.02

    return {
        "score": round(max(-0.1, min(0.35, score)), 3),
        "current_goal_title": current_goal_title,
        "current_goal_next_action": current_goal_next_action,
        "action_bias": action_bias,
        "matched_request_terms": matched_request_terms,
        "matched_step_terms": matched_step_terms,
    }


def _feedback_path(cwd: str) -> Path:
    path = Path(cwd).resolve() / ".zero_os" / "assistant" / "planner_feedback.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _default_feedback() -> dict[str, Any]:
    return {"schema_version": PLANNER_FEEDBACK_SCHEMA_VERSION, "history": [], "summary": {}}


def _load_feedback(cwd: str) -> dict[str, Any]:
    path = _feedback_path(cwd)
    if not path.exists():
        return _default_feedback()
    try:
        raw = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return _default_feedback()
    if not isinstance(raw, dict):
        return _default_feedback()
    raw.setdefault("schema_version", PLANNER_FEEDBACK_SCHEMA_VERSION)
    raw.setdefault("history", [])
    raw.setdefault("summary", {})
    return raw


def _save_feedback(cwd: str, payload: dict[str, Any]) -> None:
    _feedback_path(cwd).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _feedback_entry_is_active(entry: dict[str, Any]) -> bool:
    try:
        schema_version = int(entry.get("feedback_schema_version", 0) or 0)
    except Exception:
        schema_version = 0
    route = str(entry.get("route", "") or "").strip()
    route_variant = str(entry.get("route_variant", "") or "").strip()
    return schema_version >= PLANNER_FEEDBACK_SCHEMA_VERSION and bool(route) and bool(route_variant)


def _feedback_metrics(entries: list[dict[str, Any]]) -> dict[str, Any]:
    total = max(1, len(entries))
    return {
        "count": len(entries),
        "contradiction_hold_rate": round(sum(1 for item in entries if item.get("contradiction_hold")) / total, 3),
        "execution_failure_rate": round(sum(1 for item in entries if not item.get("ok", False)) / total, 3),
        "approval_required_surprise_rate": round(sum(1 for item in entries if item.get("approval_required_surprise")) / total, 3),
        "target_drop_rate": round(sum(int(item.get("target_drop_count", 0)) for item in entries) / total, 3),
        "successful_completion_rate": round(sum(1 for item in entries if item.get("ok", False)) / total, 3),
        "reroute_after_failure_rate": round(sum(1 for item in entries if item.get("rerouted_after_failure")) / total, 3),
    }


def _summarize_feedback(data: dict[str, Any]) -> dict[str, Any]:
    history = [dict(item) for item in list(data.get("history", [])) if isinstance(item, dict)]
    active_entries = [item for item in history if _feedback_entry_is_active(item)]
    legacy_entries = [item for item in history if not _feedback_entry_is_active(item)]

    routes_summary: dict[str, Any] = {}
    route_names = sorted({str(item.get("route", "")) for item in active_entries if str(item.get("route", ""))})
    for route_name in route_names:
        route_entries = [item for item in active_entries if str(item.get("route", "")) == route_name]
        routes_summary[route_name] = _feedback_metrics(route_entries)

    route_variants_summary: dict[str, Any] = {}
    route_variant_names = sorted({str(item.get("route_variant", "")) for item in active_entries if str(item.get("route_variant", ""))})
    for route_variant_name in route_variant_names:
        route_variant_entries = [item for item in active_entries if str(item.get("route_variant", "")) == route_variant_name]
        route_variants_summary[route_variant_name] = _feedback_metrics(route_variant_entries)

    data["summary"] = {
        "history_count": len(active_entries),
        "active_history_count": len(active_entries),
        "total_history_count": len(history),
        "legacy_history_count": len(legacy_entries),
        "routes": routes_summary,
        "route_variants": route_variants_summary,
    }
    return data


def _metrics_quality_bias(metrics: dict[str, Any]) -> float:
    count = int(metrics.get("count", 0) or 0)
    if count < 2:
        return 0.0
    success = float(metrics.get("successful_completion_rate", 0.0) or 0.0)
    hold = float(metrics.get("contradiction_hold_rate", 0.0) or 0.0)
    failure = float(metrics.get("execution_failure_rate", 0.0) or 0.0)
    target_drop = float(metrics.get("target_drop_rate", 0.0) or 0.0)
    reroute = float(metrics.get("reroute_after_failure_rate", 0.0) or 0.0)
    approval_surprise = float(metrics.get("approval_required_surprise_rate", 0.0) or 0.0)
    quality = success - (hold * 0.45) - (failure * 0.35) - (target_drop * 0.25) - (reroute * 0.15) - (approval_surprise * 0.1)
    value = round(max(-0.18, min(0.18, (quality - 0.55) * 0.3)), 3)
    return value if abs(value) >= 0.01 else 0.0


def _route_history_bias(cwd: str) -> dict[str, float]:
    summary = dict(_load_feedback(cwd).get("summary") or {})
    routes = dict(summary.get("routes") or {})
    bias: dict[str, float] = {}
    for route_name, metrics in routes.items():
        value = _metrics_quality_bias(dict(metrics or {}))
        if abs(value) >= 0.01:
            bias[str(route_name)] = value
    return bias


def _route_variant_history_bias(cwd: str) -> dict[str, float]:
    summary = dict(_load_feedback(cwd).get("summary") or {})
    route_variants = dict(summary.get("route_variants") or {})
    bias: dict[str, float] = {}
    for route_variant, metrics in route_variants.items():
        value = _metrics_quality_bias(dict(metrics or {}))
        if abs(value) >= 0.01:
            bias[str(route_variant)] = value
    return bias


def _stringify_target(value: Any) -> str:
    if isinstance(value, dict):
        return " ".join(_stringify_target(item) for item in value.values() if _stringify_target(item))
    if isinstance(value, (list, tuple, set)):
        return " ".join(_stringify_target(item) for item in value if _stringify_target(item))
    return str(value or "").strip()


def _step_action_hints(step: dict[str, Any]) -> set[str]:
    kind = str(step.get("kind", ""))
    target = step.get("target")
    if kind == "browser_open":
        return {"open"}
    if kind == "browser_action":
        action = str(dict(target or {}).get("action", "")).strip().lower()
        return {"input"} if action == "input" else {action} if action else {"click"}
    if kind in {"web_verify", "browser_dom_inspect", "flow_monitor"}:
        return {"inspect"}
    if kind in {"web_fetch", "highway_dispatch"}:
        target_text = _stringify_target(target).lower()
        if "show" in target_text or "read" in target_text:
            return {"show"}
        return {"fetch"}
    if kind in {"browser_status", "system_status", "store_status", "internet_capability", "world_class_readiness"}:
        return {"status"}
    if kind == "store_install":
        return {"install"}
    if kind == "cloud_deploy":
        return {"deploy"}
    if kind == "cloud_target_set":
        return {"configure", "deploy"}
    if kind == "recover":
        return {"recover"}
    if kind == "self_repair":
        return {"repair"}
    if kind.endswith("_plan") or kind == "controller_registry":
        return {"plan"}
    if kind.endswith("_reply_post"):
        return {"reply", "post"}
    if kind.endswith("_reply_draft"):
        return {"reply"}
    if kind.endswith("_act"):
        return {"act"}
    return set()


def _step_sequence_rank(step: dict[str, Any]) -> int:
    kind = str(step.get("kind", ""))
    if kind in _VERIFICATION_PRIORITY_KINDS:
        return 0
    if kind in {"web_fetch", "api_request", "api_workflow", "highway_dispatch"} or kind.endswith("_read") or kind.endswith("_comments") or kind.endswith("_plan"):
        return 1
    if kind in {"browser_open", "cloud_target_set", "github_issue_reply_draft", "github_pr_reply_draft"}:
        return 2
    if step_allows_mutation(kind):
        return 3
    return 2


def _planner_route_variant(plan: dict[str, Any]) -> str:
    explicit_variant = str(plan.get("route_variant", "") or "").strip()
    if explicit_variant:
        return explicit_variant
    request_text = str(plan.get("request", "") or "").strip().lower()
    step_kinds = {str(step.get("kind", "")).strip() for step in list(plan.get("steps", [])) if str(step.get("kind", "")).strip()}
    browser_actions = {
        str(dict(step.get("target") or {}).get("action", "") or "").strip().lower()
        for step in list(plan.get("steps", []))
        if str(step.get("kind", "")).strip() == "browser_action"
    }
    for variant in (
        "github_issue_reply_post",
        "github_issue_reply_draft",
        "github_issue_act",
        "github_issue_plan",
        "github_issue_comments",
        "github_issue_read",
        "github_pr_reply_post",
        "github_pr_reply_draft",
        "github_pr_act",
        "github_pr_plan",
        "github_pr_comments",
        "github_pr_read",
    ):
        if variant in step_kinds:
            return variant
    if "submit" in browser_actions:
        return "browser_submit"
    if browser_actions & {"input", "type", "fill", "enter_text"}:
        return "browser_input"
    if "click" in browser_actions:
        return "browser_click"
    if "browser_status" in step_kinds:
        return "browser_status"
    if "browser_dom_inspect" in step_kinds:
        return "browser_inspect"
    if "browser_open" in step_kinds:
        return "browser_open"
    if "web_verify" in step_kinds and not (step_kinds & {"browser_open", "browser_action", "web_fetch"}):
        return "web_verify"
    if "web_fetch" in step_kinds and not (step_kinds & {"browser_open", "browser_action"}):
        return "web_fetch"
    if "cloud_deploy" in step_kinds:
        return "cloud_deploy"
    if "cloud_target_set" in step_kinds:
        return "cloud_target_set"
    if "code_change" in step_kinds:
        return "code_change"
    if any(kind.startswith("github_issue_") for kind in step_kinds):
        return "github_issue"
    if any(kind.startswith("github_pr_") for kind in step_kinds):
        return "github_pr"
    if "github" in request_text and "status" in request_text:
        return "github_status"
    if "system_status" in step_kinds:
        return "system_status"
    return str(((plan.get("intent") or {}).get("primary_intent") or (plan.get("intent") or {}).get("intent") or "observe")).strip() or "observe"


def _attach_target_hints_to_subgoals(decomposition: list[dict[str, Any]], targets: dict[str, Any]) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    for subgoal in decomposition:
        updated = dict(subgoal)
        text_lower = str(updated.get("text", "")).lower()
        attached_target_ids: list[str] = []
        target_values: list[str] = []
        for item in list(targets.get("items", [])):
            target_id = str(item.get("id", ""))
            label = str(item.get("label", "")).strip().lower()
            value_text = _stringify_target(item.get("value")).lower()
            matches = [candidate for candidate in (label, value_text) if candidate and candidate in text_lower]
            if matches:
                attached_target_ids.append(target_id)
                target_values.extend(matches)
        updated["attached_target_ids"] = list(dict.fromkeys(attached_target_ids))
        updated["target_values"] = list(dict.fromkeys(target_values))
        enriched.append(updated)
    return enriched


def _subgoal_execution_order(decomposition: list[dict[str, Any]]) -> dict[str, int]:
    by_id = {str(item.get("id", "")): dict(item) for item in decomposition if str(item.get("id", ""))}
    indegree = {item_id: 0 for item_id in by_id}
    outgoing: dict[str, list[str]] = {item_id: [] for item_id in by_id}
    for item_id, item in by_id.items():
        for dependency in [str(dep) for dep in list(item.get("depends_on", [])) if str(dep)]:
            if dependency not in by_id:
                continue
            indegree[item_id] += 1
            outgoing.setdefault(dependency, []).append(item_id)
    ready = sorted((item_id for item_id, degree in indegree.items() if degree == 0), key=lambda item_id: int(by_id[item_id].get("order", 0)))
    order: dict[str, int] = {}
    cursor = 0
    while ready:
        current = ready.pop(0)
        order[current] = cursor
        cursor += 1
        for dependent in sorted(outgoing.get(current, []), key=lambda item_id: int(by_id[item_id].get("order", 0))):
            indegree[dependent] -= 1
            if indegree[dependent] == 0:
                ready.append(dependent)
        ready.sort(key=lambda item_id: int(by_id[item_id].get("order", 0)))
    for item_id in sorted(by_id, key=lambda name: int(by_id[name].get("order", 0))):
        if item_id not in order:
            order[item_id] = cursor
            cursor += 1
    return order


def _dependency_depth(decomposition: list[dict[str, Any]]) -> int:
    by_id = {str(item.get("id", "")): dict(item) for item in decomposition if str(item.get("id", ""))}

    def depth(item_id: str, seen: set[str]) -> int:
        if item_id in seen:
            return 0
        current = by_id.get(item_id, {})
        dependencies = [str(dep) for dep in list(current.get("depends_on", [])) if str(dep)]
        if not dependencies:
            return 0
        next_seen = set(seen)
        next_seen.add(item_id)
        return 1 + max(depth(dep, next_seen) for dep in dependencies if dep in by_id)

    return max((depth(item_id, set()) for item_id in by_id), default=0)


def _match_step_to_subgoal(step: dict[str, Any], decomposition: list[dict[str, Any]]) -> dict[str, Any] | None:
    attached_targets = set(str(item) for item in list(step.get("attached_targets", [])) if str(item))
    step_text = _stringify_target(step.get("target")).lower()
    step_actions = _step_action_hints(step)
    original_subgoal = str(step.get("subgoal_id", ""))
    best_match: dict[str, Any] | None = None
    best_score = -1.0
    for subgoal in decomposition:
        score = 0.0
        subgoal_target_ids = set(str(item) for item in list(subgoal.get("attached_target_ids", [])) if str(item))
        if attached_targets and subgoal_target_ids:
            score += float(len(attached_targets & subgoal_target_ids)) * 3.0
        if original_subgoal and original_subgoal == str(subgoal.get("id", "")):
            score += 2.0
        if original_subgoal and original_subgoal in subgoal_target_ids:
            score += 1.5
        target_values = [str(value).lower() for value in list(subgoal.get("target_values", []))]
        if target_values and any(value in step_text for value in target_values):
            score += 2.0
        subgoal_actions = set(str(item) for item in list(subgoal.get("action_hints", [])) if str(item))
        if step_actions and subgoal_actions:
            score += float(len(step_actions & subgoal_actions)) * 1.6
        if bool(subgoal.get("blocking")) and str(step.get("kind", "")) in _VERIFICATION_PRIORITY_KINDS:
            score += 0.6
        if score > best_score:
            best_score = score
            best_match = subgoal
    return best_match if best_score > 0.0 else None


def _attach_step_decomposition(steps: list[dict[str, Any]], decomposition: list[dict[str, Any]], targets: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    enriched_decomposition = _attach_target_hints_to_subgoals(decomposition, targets)
    execution_order = _subgoal_execution_order(enriched_decomposition)
    for subgoal in enriched_decomposition:
        subgoal["execution_order_hint"] = int(execution_order.get(str(subgoal.get("id", "")), int(subgoal.get("order", 0))))

    sortable_steps: list[tuple[int, dict[str, Any]]] = []
    for original_index, step in enumerate(steps):
        updated = dict(step)
        matched = _match_step_to_subgoal(updated, enriched_decomposition)
        if matched:
            updated["decomposition_subgoal_id"] = str(matched.get("id", ""))
            updated["decomposition_order"] = int(matched.get("execution_order_hint", matched.get("order", original_index)))
            updated["decomposition_dependency_kind"] = str(matched.get("dependency_kind", "parallel"))
            updated["decomposition_depends_on"] = [str(item) for item in list(matched.get("depends_on", [])) if str(item)]
            updated["decomposition_blocking"] = bool(matched.get("blocking", False))
            updated["decomposition_conditional"] = bool(matched.get("conditional", False))
            condition_type = str(matched.get("condition_type", "always"))
            if condition_type in {"on_failure", "on_success", "on_verified"}:
                updated["conditional_execution_mode"] = condition_type
            else:
                updated["conditional_execution_mode"] = "always"
            updated["condition_type"] = str(matched.get("condition_type", "always"))
            updated["condition_trigger_text"] = str(matched.get("condition_trigger_text", ""))
            updated["condition_trigger_hints"] = [str(item) for item in list(matched.get("condition_trigger_hints", [])) if str(item)]
        else:
            updated["decomposition_subgoal_id"] = str(updated.get("subgoal_id", ""))
            updated["decomposition_order"] = original_index
            updated["decomposition_dependency_kind"] = "unmatched"
            updated["decomposition_depends_on"] = []
            updated["decomposition_blocking"] = False
            updated["decomposition_conditional"] = False
            updated["conditional_execution_mode"] = "always"
            updated["condition_type"] = "always"
            updated["condition_trigger_text"] = ""
            updated["condition_trigger_hints"] = []
        sortable_steps.append((original_index, updated))

    sorted_steps = [
        step
        for _, step in sorted(
            sortable_steps,
            key=lambda item: (
                0
                if str(item[1].get("kind", "")) == "web_verify" and list(item[1].get("attached_targets", []))
                else 1
                if str(item[1].get("kind", "")) in _VERIFICATION_PRIORITY_KINDS
                else 2,
                int(item[1].get("decomposition_order", item[0])),
                _step_sequence_rank(item[1]),
                0 if str(item[1].get("risk_level", "")) == "low" else 1 if str(item[1].get("risk_level", "")) == "medium" else 2,
                -float(item[1].get("route_confidence", 0.0) or 0.0),
                item[0],
            ),
        )
    ]
    return sorted_steps, enriched_decomposition


def _annotate_step_causality(steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    indexed = [dict(step) for step in steps]
    by_subgoal: dict[str, list[int]] = {}
    subgoal_dependencies: dict[str, set[str]] = {}
    for index, step in enumerate(indexed):
        subgoal_id = str(step.get("decomposition_subgoal_id", "") or step.get("subgoal_id", ""))
        if subgoal_id:
            by_subgoal.setdefault(subgoal_id, []).append(index)
            subgoal_dependencies.setdefault(subgoal_id, set()).update(
                str(item) for item in list(step.get("decomposition_depends_on", [])) if str(item)
            )

    reverse_subgoal_dependents: dict[str, set[str]] = {}
    for subgoal_id, depends_on in subgoal_dependencies.items():
        for prerequisite in depends_on:
            reverse_subgoal_dependents.setdefault(prerequisite, set()).add(subgoal_id)

    dependent_cache: dict[str, set[str]] = {}

    def _transitive_dependents(subgoal_id: str) -> set[str]:
        if subgoal_id in dependent_cache:
            return set(dependent_cache[subgoal_id])
        visited: set[str] = set()
        stack = list(reverse_subgoal_dependents.get(subgoal_id, set()))
        while stack:
            candidate = stack.pop()
            if candidate in visited:
                continue
            visited.add(candidate)
            stack.extend(reverse_subgoal_dependents.get(candidate, set()))
        dependent_cache[subgoal_id] = set(visited)
        return set(visited)

    for index, step in enumerate(indexed):
        depends_on = [str(item) for item in list(step.get("decomposition_depends_on", [])) if str(item)]
        subgoal_id = str(step.get("decomposition_subgoal_id", "") or step.get("subgoal_id", ""))
        impacted_indexes: list[int] = []
        if subgoal_id:
            impacted_indexes.extend(item for item in by_subgoal.get(subgoal_id, []) if item > index)
            for dependent_subgoal in _transitive_dependents(subgoal_id):
                impacted_indexes.extend(item for item in by_subgoal.get(dependent_subgoal, []) if item > index)
        else:
            impacted_indexes.extend(
                item
                for item in range(index + 1, len(indexed))
                if indexed[item].get("decomposition_order", 0) >= step.get("decomposition_order", 0)
            )
        impacted = sorted(set(impacted_indexes))
        failure_impact_mode = "local_step_only"
        dependency_strength = "soft"
        dependency_kind = str(step.get("decomposition_dependency_kind", ""))
        if depends_on or dependency_kind in {"sequential", "prerequisite", "conditional"}:
            dependency_strength = "hard" if dependency_kind in {"sequential", "prerequisite"} else "soft"
            failure_impact_mode = "blocks_dependent_steps" if dependency_kind != "conditional" else "conditional_branch_invalidated"
        elif bool(step.get("mutation_requested_explicitly", False)):
            failure_impact_mode = "verification_required_before_continue"
            dependency_strength = "soft"
        conditional_mode = str(step.get("conditional_execution_mode", "always"))
        if conditional_mode == "on_failure":
            dependency_strength = "soft"
            failure_impact_mode = "activated_only_if_prior_step_fails"
        elif conditional_mode == "on_success":
            dependency_strength = "soft"
            failure_impact_mode = "activated_only_if_prior_step_succeeds"
        elif conditional_mode == "on_verified":
            dependency_strength = "soft"
            failure_impact_mode = "activated_only_if_prior_verification_succeeds"

        blocks = [str(indexed[item].get("kind", "")) for item in impacted[:6] if dependency_strength == "hard"]
        degrades: list[str] = []
        if dependency_strength != "hard":
            degrades = [str(indexed[item].get("kind", "")) for item in impacted[:6]]
        if bool(step.get("mutation_requested_explicitly", False)) and "post_action_verification" == str(step.get("verification_mode", "")):
            degrades.append("post_action_verification")
        degrades = list(dict.fromkeys([item for item in degrades if item]))

        step["dependency_strength"] = dependency_strength
        step["failure_impact"] = {
            "mode": failure_impact_mode,
            "blocks": blocks,
            "degrades": degrades,
        }
        step["failure_impact_label"] = failure_impact_mode
        step["invalidates_if_failed"] = [str(indexed[item].get("kind", "")) for item in impacted[:6]]
        step["dependent_step_count"] = len(impacted)
        step["executes_on_failure_of"] = depends_on if conditional_mode == "on_failure" else []
        step["executes_on_success_of"] = depends_on if conditional_mode == "on_success" else []
        step["executes_on_verified_of"] = depends_on if conditional_mode == "on_verified" else []
    return indexed


def _annotate_step_reasoning(steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    enriched = [dict(step) for step in steps]
    for index, step in enumerate(enriched):
        requires = [str(item) for item in list(step.get("decomposition_depends_on", [])) if str(item)]
        prior_kinds = [str(item.get("kind", "")) for item in enriched[:index]]
        kind = str(step.get("kind", ""))
        if kind == "browser_action" and "browser_open" in prior_kinds and "browser_open" not in requires:
            requires.append("browser_open")
        if kind == "web_fetch" and "web_verify" in prior_kinds and "web_verify" not in requires:
            requires.append("web_verify")
        if kind == "cloud_deploy" and "cloud_target_set" in prior_kinds and "cloud_target_set" not in requires:
            requires.append("cloud_target_set")

        failure_impact = dict(step.get("failure_impact") or {})
        enables = list(dict.fromkeys([str(item) for item in list(failure_impact.get("blocks", [])) + list(failure_impact.get("degrades", [])) if str(item)]))
        breaks_if_failed = [str(item) for item in list(failure_impact.get("blocks", [])) if str(item)] or enables
        route_confidence = float(step.get("route_confidence", 0.0) or 0.0)
        uncertainty = 1.0 - route_confidence
        if str(step.get("precondition_state", "")) == "degraded":
            uncertainty += 0.12
        elif str(step.get("precondition_state", "")) == "blocked":
            uncertainty += 0.2
        if str(step.get("dependency_strength", "")) == "hard":
            uncertainty += 0.08
        if str(step.get("conditional_execution_mode", "always")) != "always":
            uncertainty += 0.06
        step["requires"] = requires
        step["enables"] = enables
        step["breaks_if_failed"] = breaks_if_failed
        step["uncertainty"] = round(max(0.05, min(0.95, uncertainty)), 3)
        step["reasoning_trace"] = {
            "why_this_step_exists": str(step.get("justification", "") or step.get("source_of_route", "")),
            "depends_on": requires,
            "resolves": [str(item) for item in list(step.get("attached_targets", [])) if str(item)] or [str(step.get("target", ""))],
            "condition": str(step.get("conditional_execution_mode", "always")),
        }
    return enriched


def _step_signature(step: dict) -> str:
    return json.dumps(
        {"kind": step.get("kind", ""), "target": step.get("target", "")},
        sort_keys=True,
        default=str,
    )


def _dedupe_steps(steps: list[dict]) -> list[dict]:
    seen: set[str] = set()
    deduped: list[dict] = []
    for step in steps:
        signature = _step_signature(step)
        if signature in seen:
            continue
        seen.add(signature)
        deduped.append(dict(step))
    return deduped


def _candidate_signature(plan: dict) -> str:
    return json.dumps(
        [
            {
                "kind": step.get("kind", ""),
                "target": step.get("target", ""),
                "subgoal_id": step.get("subgoal_id", ""),
            }
            for step in list(plan.get("steps", []))
        ],
        sort_keys=True,
        default=str,
    )


def _candidate_semantic_signature(plan: dict) -> str:
    branch = dict(plan.get("branch") or {})
    normalized_steps = [
        json.dumps(
            {
                "kind": step.get("kind", ""),
                "target": step.get("target", ""),
                "attached_targets": sorted(str(item) for item in list(step.get("attached_targets", [])) if str(item)),
                "mutation": bool(step.get("mutation_requested_explicitly", False)),
            },
            sort_keys=True,
            default=str,
        )
        for step in list(plan.get("steps", []))
    ]
    return json.dumps(
        {
            "memory_mode": str(branch.get("memory_mode", "balanced")),
            "risk_level": str(plan.get("risk_level", "")),
            "steps": normalized_steps,
        },
        sort_keys=True,
        default=str,
    )


def _candidate_quality(plan: dict) -> tuple[Any, ...]:
    branch = dict(plan.get("branch") or {})
    coverage = dict(plan.get("target_coverage") or {})
    steps = list(plan.get("steps", []))
    average_step_confidence = sum(float(step.get("route_confidence", 0.0) or 0.0) for step in steps) / max(1, len(steps))
    return (
        1 if bool(branch.get("preferred", False)) else 0,
        float(dict(plan.get("survivor_history_prior") or {}).get("score", 0.0) or 0.0),
        float(plan.get("route_variant_history_bias", 0.0) or 0.0),
        float(plan.get("planner_confidence", 0.0) or 0.0),
        float(coverage.get("coverage_ratio", 0.0) or 0.0),
        -len(list(plan.get("ambiguity_flags", []))),
        average_step_confidence,
    )


def _add_candidate(candidates: list[dict], exact_seen: set[str], semantic_seen: dict[str, int], plan: dict) -> None:
    exact_signature = _candidate_signature(plan)
    if exact_signature in exact_seen:
        return
    exact_seen.add(exact_signature)
    semantic_signature = _candidate_semantic_signature(plan)
    existing_index = semantic_seen.get(semantic_signature)
    if existing_index is None:
        semantic_seen[semantic_signature] = len(candidates)
        candidates.append(plan)
        return
    if _candidate_quality(plan) > _candidate_quality(candidates[existing_index]):
        candidates[existing_index] = plan


def _clone_plan(plan: dict, steps: list[dict], *, branch_id: str, source: str, note: str, preferred: bool = False, memory_mode: str | None = None) -> dict:
    cloned = deepcopy(plan)
    cloned["steps"] = [dict(step) for step in steps]
    cloned["branch"] = {
        "id": branch_id,
        "source": source,
        "note": note,
        "preferred": bool(preferred),
        "memory_mode": memory_mode or str((plan.get("branch") or {}).get("memory_mode", "balanced")),
    }
    cloned["branch_reason"] = note
    return cloned


def _attach_branch_support(
    cwd: str,
    plan: dict,
    memory_context: dict,
    *,
    memory_mode: str,
    route_variant_bias_map: dict[str, float] | None = None,
) -> dict:
    enriched = deepcopy(plan)
    memory_summary = _memory_context_summary(memory_context, mode=memory_mode)
    targets = dict(enriched.get("request_targets", {}) or enriched.get("targets", {}))
    request_decomposition = [dict(item) for item in list(enriched.get("request_decomposition", []))]
    steps = [dict(step) for step in list(enriched.get("steps", []))]
    attached = bool(steps) and all(
        "decomposition_order" in step or "decomposition_subgoal_id" in step or "subgoal_id" in step
        for step in steps
    )
    evaluated = _evaluate_primary_shape(
        steps,
        request_decomposition,
        targets,
        attached=attached,
        intent_confidence=float(enriched.get("intent_confidence", 0.5) or 0.5),
        ambiguity_flags=list(enriched.get("ambiguity_flags", [])),
        conflicting_signals=list(enriched.get("conflicting_signals", [])),
        route_history_bias=dict(enriched.get("route_history_bias", {})),
        read_only_request=bool(enriched.get("read_only_request", False)),
        memory_strength=str(memory_summary.get("memory_strength", "none")),
    )
    enriched["steps"] = list(evaluated.get("steps", []))
    enriched["request_decomposition"] = list(evaluated.get("request_decomposition", request_decomposition))
    enriched["planner_precheck"] = dict(evaluated.get("precheck", {}))
    enriched["plan_simulation"] = dict(evaluated.get("simulation", {}))
    enriched["planner_confidence"] = float(evaluated.get("planner_confidence", enriched.get("planner_confidence", 0.0)) or 0.0)
    enriched["risk_level"] = str(evaluated.get("risk_level", _plan_risk_level(list(enriched.get("steps", [])))))
    enriched["risk"] = enriched["risk_level"]
    enriched["predicted_risk"] = str((enriched.get("plan_simulation") or {}).get("predicted_risk", enriched.get("risk_level", "low")))
    enriched["expected_success"] = float((enriched.get("plan_simulation") or {}).get("expected_success", enriched.get("planner_confidence", 0.0)) or 0.0)
    enriched["memory_context"] = memory_summary
    ambiguity_flags = list(dict.fromkeys(list(enriched.get("ambiguity_flags", [])) + list(evaluated.get("ambiguity_flags", []))))
    coverage = dict(evaluated.get("coverage", _coverage_for_steps(targets, list(enriched.get("steps", [])))))
    if coverage.get("unbound_targets"):
        ambiguity_flags.extend(["unbound_explicit_targets", "dropped_target"])
    enriched["ambiguity_flags"] = list(dict.fromkeys(ambiguity_flags))
    enriched["ambiguity"] = list(enriched["ambiguity_flags"])
    enriched["target_coverage"] = coverage
    enriched["dropped_targets"] = list(coverage.get("unbound_targets", []))
    enriched["route_confidence_by_step"] = {
        str(index): float(step.get("route_confidence", 0.0) or 0.0)
        for index, step in enumerate(list(enriched.get("steps", [])))
    }
    enriched["evidence"] = score_branch_support(enriched, memory_context)
    enriched["memory_dependency"] = float(enriched["evidence"].get("memory_weight", 0.0) or 0.0)
    route_variant = _planner_route_variant(enriched)
    route_variant_bias = float(dict(route_variant_bias_map or {}).get(route_variant, 0.0) or 0.0)
    enriched["route_variant"] = route_variant
    enriched["route_surface"] = route_variant
    enriched["route_variant_history_bias"] = round(route_variant_bias, 3)
    branch = dict(enriched.get("branch") or {})
    branch["route_variant"] = route_variant
    branch["route_surface"] = route_variant
    enriched["branch"] = branch
    return enriched


def _branch_rejection_state(plan: dict[str, Any]) -> dict[str, Any]:
    simulation = dict(plan.get("plan_simulation") or {})
    precheck = dict(plan.get("planner_precheck") or {})
    coverage = dict(plan.get("target_coverage") or {})
    planner_confidence = float(plan.get("planner_confidence", 0.0) or 0.0)
    expected_success = float(simulation.get("expected_success", planner_confidence) or 0.0)
    predicted_risk = str(simulation.get("predicted_risk", plan.get("risk_level", "low")) or "low").lower()
    mutating = any(step_allows_mutation(str(step.get("kind", ""))) for step in list(plan.get("steps", [])))
    verification_count = int(simulation.get("verification_count", 0) or 0)
    coverage_ratio = float(coverage.get("coverage_ratio", 0.0) or 0.0)
    high_conflict = any(str(item.get("severity", "")) == "high" for item in list(precheck.get("issues", [])))
    branch = dict(plan.get("branch") or {})
    branch_id = str(branch.get("id", ""))
    branch_source = str(branch.get("source", ""))
    exempt_target_isolation = branch_source == "target_specific_branch" or branch_id.startswith("single_target_")
    exempt_single_remediation = branch_source == "single_remediation_regeneration" or branch_id in {"single_recover", "single_self_repair"}
    coverage_sensitive = not (exempt_target_isolation or exempt_single_remediation)
    reasons: list[str] = []

    if mutating and coverage_ratio < 1.0 and coverage_sensitive:
        reasons.append("mutating_branch_drops_targets")
    if high_conflict and expected_success < 0.72 and not exempt_target_isolation:
        reasons.append("high_conflict_low_success")
    if expected_success < 0.34 and not (exempt_target_isolation or exempt_single_remediation):
        reasons.append("predicted_success_too_low")
    if mutating and planner_confidence < 0.35:
        reasons.append("planner_confidence_too_low_for_mutation")
    if mutating and predicted_risk == "high" and verification_count == 0 and not exempt_target_isolation:
        reasons.append("unverified_high_risk_mutation")

    return {
        "rejected": bool(reasons),
        "reasons": reasons,
        "expected_success": round(expected_success, 3),
        "predicted_risk": predicted_risk,
        "coverage_ratio": round(coverage_ratio, 3),
        "conflict_count": int(precheck.get("conflict_count", 0) or 0),
    }


def _evaluate_primary_shape(
    steps: list[dict[str, Any]],
    request_decomposition: list[dict[str, Any]],
    targets: dict[str, Any],
    *,
    attached: bool = False,
    intent_confidence: float,
    ambiguity_flags: list[str],
    conflicting_signals: list[str],
    route_history_bias: dict[str, float],
    read_only_request: bool,
    memory_strength: str,
) -> dict[str, Any]:
    if attached:
        shaped_steps = [dict(step) for step in steps]
        shaped_decomposition = [dict(item) for item in request_decomposition]
    else:
        shaped_steps, shaped_decomposition = _attach_step_decomposition([dict(step) for step in steps], [dict(item) for item in request_decomposition], targets)
    shaped_steps = _annotate_step_causality(shaped_steps)
    precheck = simulate_plan_conflicts(shaped_steps, shaped_decomposition, targets, read_only_request=read_only_request)
    shaped_steps, precondition_flags = _annotate_step_contracts(shaped_steps)
    shaped_steps = _annotate_step_reasoning(shaped_steps)
    coverage = _coverage_for_steps(targets, shaped_steps)
    combined_ambiguity = list(dict.fromkeys(list(ambiguity_flags) + list(precondition_flags)))
    planner_confidence = _planner_confidence(
        float(intent_confidence or 0.0),
        float(coverage.get("coverage_ratio", 0.0) or 0.0),
        len(combined_ambiguity),
        len(set(conflicting_signals)),
        len(list(coverage.get("unbound_targets", []))),
    )
    planner_confidence = max(
        0.0,
        round(
            planner_confidence
            - float(precheck.get("confidence_adjustment", 0.0) or 0.0)
            - (0.08 if memory_strength == "conflicting" else 0.0)
            - min(0.08, _dependency_depth(shaped_decomposition) * 0.02),
            3,
        ),
    )
    risk_level = _plan_risk_level(shaped_steps)
    simulation = simulate_plan(
        list(shaped_steps),
        list(shaped_decomposition),
        dict(targets),
        planner_confidence=planner_confidence,
        risk_level=str(risk_level),
        ambiguity_flags=combined_ambiguity,
        route_history_bias=dict(route_history_bias),
        precheck=precheck,
        memory_strength=memory_strength,
    )
    return {
        "steps": shaped_steps,
        "request_decomposition": shaped_decomposition,
        "precheck": precheck,
        "precondition_flags": precondition_flags,
        "coverage": coverage,
        "planner_confidence": planner_confidence,
        "risk_level": risk_level,
        "simulation": simulation,
        "ambiguity_flags": combined_ambiguity,
    }


def _maybe_apply_survivor_guidance_to_primary(
    cwd: str,
    steps: list[dict[str, Any]],
    request_decomposition: list[dict[str, Any]],
    targets: dict[str, Any],
    *,
    attached: bool = False,
    reasoning_trace: dict[str, Any],
    read_only_request: bool,
    intent_confidence: float,
    ambiguity_flags: list[str],
    conflicting_signals: list[str],
    route_history_bias: dict[str, float],
    memory_strength: str,
) -> dict[str, Any]:
    provisional_plan = {
        "steps": [dict(step) for step in steps],
        "request_targets": dict(targets),
        "reasoning_trace": dict(reasoning_trace),
    }
    guidance = survivor_generation_guidance(cwd, provisional_plan)
    current_prior = survivor_history_score(cwd, provisional_plan)
    result = {
        "steps": [dict(step) for step in steps],
        "guidance": guidance,
        "applied": False,
        "applied_pattern": "",
        "applied_score": 0.0,
        "current_prior": current_prior,
    }
    if not bool(guidance.get("history_ready")) or _dependency_depth(request_decomposition) > 0:
        return result

    baseline = _evaluate_primary_shape(
        list(steps),
        request_decomposition,
        targets,
        attached=attached,
        intent_confidence=intent_confidence,
        ambiguity_flags=ambiguity_flags,
        conflicting_signals=conflicting_signals,
        route_history_bias=route_history_bias,
        read_only_request=read_only_request,
        memory_strength=memory_strength,
    )
    baseline_conflicts = int(dict(baseline.get("precheck") or {}).get("conflict_count", 0) or 0)
    baseline_success = float(dict(baseline.get("simulation") or {}).get("expected_success", 0.0) or 0.0)

    for recommendation in list(guidance.get("recommended_patterns", [])):
        pattern_signature = str(recommendation.get("pattern_signature", "")).strip()
        if not pattern_signature or not pattern_signature.startswith("verify"):
            continue
        if float(recommendation.get("score", 0.0) or 0.0) <= float(current_prior.get("score", 0.0) or 0.0) + 0.08:
            continue
        candidate_steps = pattern_guided_steps(list(steps), pattern_signature)
        if _candidate_signature({"steps": candidate_steps}) == _candidate_signature({"steps": steps}):
            continue
        candidate = _evaluate_primary_shape(
            candidate_steps,
            request_decomposition,
            targets,
            attached=attached,
            intent_confidence=intent_confidence,
            ambiguity_flags=ambiguity_flags,
            conflicting_signals=conflicting_signals,
            route_history_bias=route_history_bias,
            read_only_request=read_only_request,
            memory_strength=memory_strength,
        )
        candidate_conflicts = int(dict(candidate.get("precheck") or {}).get("conflict_count", 0) or 0)
        candidate_success = float(dict(candidate.get("simulation") or {}).get("expected_success", 0.0) or 0.0)
        if candidate_conflicts > baseline_conflicts:
            continue
        if candidate_success + 0.001 < baseline_success:
            continue
        result["steps"] = [dict(step) for step in candidate_steps]
        result["applied"] = True
        result["applied_pattern"] = pattern_signature
        result["applied_score"] = float(recommendation.get("score", 0.0) or 0.0)
        break
    return result


def build_candidate_plans(request: str, cwd: str = ".", base_plan: dict | None = None) -> dict:
    primary = deepcopy(base_plan) if base_plan else build_plan(request, cwd, memory_mode="balanced")
    request_text = str(primary.get("request", _normalize_text(request)))
    memory_context = build_memory_context(cwd, request_text, dict(primary.get("intent", {})))
    memory_free_context = _strip_memory_context(memory_context)
    route_variant_bias_map = _route_variant_history_bias(cwd)
    survivor_guidance = survivor_generation_guidance(cwd, primary)
    strategy_guidance = dict(primary.get("survivor_strategy_guidance") or {})
    candidates: list[dict] = []
    rejected_candidates: list[dict] = []
    exact_seen: set[str] = set()
    semantic_seen: dict[str, int] = {}

    def add(plan: dict, *, memory_ctx: dict, memory_mode: str) -> None:
        attached = _attach_branch_support(
            cwd,
            plan,
            memory_ctx,
            memory_mode=memory_mode,
            route_variant_bias_map=route_variant_bias_map,
        )
        attached["branch_rejection"] = _branch_rejection_state(attached)
        if bool(dict(attached.get("branch_rejection") or {}).get("rejected", False)):
            rejected_candidates.append(attached)
            return
        coverage = dict(attached.get("target_coverage", {}))
        if not attached.get("planner_confidence"):
            attached["planner_confidence"] = _planner_confidence(
                float(attached.get("intent_confidence", 0.5) or 0.5),
                float(coverage.get("coverage_ratio", 0.0) or 0.0),
                len(list(attached.get("ambiguity_flags", []))),
                len(list(attached.get("conflicting_signals", []))),
                len(list(coverage.get("unbound_targets", []))),
            )
        attached["goal_alignment"] = _goal_alignment_score(
            request_text,
            attached,
            dict(attached.get("world_model_context") or primary.get("world_model_context") or {}),
        )
        attached["survivor_history_prior"] = survivor_history_score(cwd, attached)
        _add_candidate(candidates, exact_seen, semantic_seen, attached)

    add(
        _clone_plan(
            primary,
            list(primary.get("steps", [])),
            branch_id=str((primary.get("branch") or {}).get("id", "primary")),
            source=str((primary.get("branch") or {}).get("source", "weighted_intent_resolution")),
            note=str((primary.get("branch") or {}).get("note", "Primary branch selected by weighted intent resolution.")),
            preferred=True,
            memory_mode="balanced",
        ),
        memory_ctx=memory_context,
        memory_mode="balanced",
    )

    for mode_name, ctx in (("supported", memory_context), ("disabled", memory_free_context)):
        branch_plan = build_plan(request_text, cwd, memory_mode=mode_name)
        add(
            _clone_plan(
                branch_plan,
                list(branch_plan.get("steps", [])),
                branch_id="memory_supported" if mode_name == "supported" else "memory_free",
                source="memory_supported_route" if mode_name == "supported" else "memory_free_route",
                note="Memory-supported branch using stronger stable-memory bias during route selection." if mode_name == "supported" else "Memory-free fallback branch that ignores working and playbook memory during route selection.",
                memory_mode=mode_name,
            ),
            memory_ctx=ctx,
            memory_mode=mode_name,
        )

    steps = list(primary.get("steps", []))
    request_lowered = request_text.lower()
    explicit_mutation = any(token in request_lowered for token in MUTATION_TOKENS)
    ambiguous_request = bool(list(primary.get("ambiguity_flags", [])))
    smart_profile = dict(primary.get("smart_planner") or {})
    guided_strategy = str(strategy_guidance.get("preferred_strategy", "")).strip().lower()
    guided_branch_types = {
        str(item).strip().lower()
        for item in list(strategy_guidance.get("preferred_branch_types", []))
        if str(item).strip()
    }
    safe_strategy = str(smart_profile.get("planner_mode", "")) == "safe" or str(smart_profile.get("strategy", "")) == "conservative"
    verification_first = sorted(
        [dict(step) for step in steps],
        key=lambda step: (
            0 if str(step.get("kind", "")) in _VERIFICATION_PRIORITY_KINDS else 1,
            0 if str(step.get("risk_level", "")) == "low" else 1,
            -float(step.get("route_confidence", 0.0) or 0.0),
        ),
    )
    add(_clone_plan(primary, verification_first, branch_id="verification_first", source="verification_first", note="Verification-first branch reorders observation and verification before mutation.", memory_mode="balanced"), memory_ctx=memory_context, memory_mode="balanced")
    if guided_strategy == "verification_first" or "verification_first" in guided_branch_types:
        add(
            _clone_plan(
                primary,
                verification_first,
                branch_id="survivor_strategy_seed",
                source="survivor_strategy_guidance",
                note="Survivor strategy guidance seeded a verification-first branch because cross-context history validated this structure.",
                memory_mode="balanced",
            ),
            memory_ctx=memory_context,
            memory_mode="balanced",
        )

    read_only_steps = [dict(step) for step in steps if str(step.get("kind", "")) in _READ_ONLY_STEP_KINDS]
    if read_only_steps and bool(primary.get("read_only_request")) and not explicit_mutation:
        add(_clone_plan(primary, read_only_steps, branch_id="read_only_inspection", source="read_only_regeneration", note="Read-only inspection branch removes mutating steps before execution.", memory_mode="balanced"), memory_ctx=memory_context, memory_mode="balanced")

    minimal_safe: list[dict] = []
    seen_subgoals: set[str] = set()
    for step in verification_first:
        subgoal_id = str(step.get("subgoal_id", ""))
        if subgoal_id in seen_subgoals:
            continue
        if str(step.get("risk_level", "")) == "low":
            minimal_safe.append(dict(step))
            seen_subgoals.add(subgoal_id)
    if not minimal_safe:
        minimal_safe = [make_step("observe", request_text, subgoal_id="observe", route_confidence=0.4, source_of_route="minimal_safe_fallback")]
    if bool(primary.get("read_only_request")) or (ambiguous_request and not explicit_mutation) or safe_strategy or guided_strategy == "conservative" or "minimal_safe" in guided_branch_types:
        add(_clone_plan(primary, minimal_safe, branch_id="minimal_safe", source="minimal_safe_branch", note="Minimal-safe branch keeps one low-risk verification step per subgoal.", memory_mode="balanced"), memory_ctx=memory_context, memory_mode="balanced")

    if bool(primary.get("read_only_request")) or (ambiguous_request and not explicit_mutation) or any(str(step.get("risk_level", "")) == "high" for step in steps) or safe_strategy or guided_strategy == "conservative" or "observation_only" in guided_branch_types:
        conservative = [dict(step) for step in steps if not step_allows_mutation(str(step.get("kind", "")))]
        if conservative:
            add(_clone_plan(primary, conservative, branch_id="conservative_execution", source="risk_conservative_branch", note="Conservative execution branch drops mutating steps while preserving observation coverage.", memory_mode="balanced"), memory_ctx=memory_context, memory_mode="balanced")

    evidence_first = sorted([dict(step) for step in steps], key=lambda step: (0 if str(step.get("verification_mode", "")) == "observe" else 1, -float(step.get("route_confidence", 0.0) or 0.0), 0 if str(step.get("risk_level", "")) == "low" else 1))
    add(_clone_plan(primary, evidence_first, branch_id="evidence_first", source="evidence_first_branch", note="Evidence-first branch prioritizes strongly-supported low-risk steps before other work.", memory_mode="balanced"), memory_ctx=memory_context, memory_mode="balanced")
    if guided_strategy == "dependency_aware" or guided_strategy == "verification_first" or "evidence_first" in guided_branch_types:
        add(
            _clone_plan(
                primary,
                evidence_first,
                branch_id="survivor_strategy_evidence",
                source="survivor_strategy_guidance",
                note="Survivor strategy guidance emphasized an evidence-first branch because validated history favored earlier verification or dependency resolution.",
                memory_mode="balanced",
            ),
            memory_ctx=memory_context,
            memory_mode="balanced",
        )

    for index, recommendation in enumerate(list(survivor_guidance.get("recommended_patterns", []))[:3]):
        pattern_signature = str(recommendation.get("pattern_signature", "")).strip()
        if not pattern_signature:
            continue
        guided_steps = pattern_guided_steps(steps, pattern_signature)
        if not guided_steps:
            continue
        add(
            _clone_plan(
                primary,
                guided_steps,
                branch_id=f"survivor_guided_{index}",
                source="survivor_history_generation",
                note=f"Survivor-guided branch aligns the plan to historically surviving pattern `{pattern_signature}` for this request context.",
                memory_mode="balanced",
            ),
            memory_ctx=memory_context,
            memory_mode="balanced",
        )

    target_items = list((primary.get("request_targets") or {}).get("items", []))
    if len(target_items) > 1 or guided_strategy == "target_isolated" or "single_target" in guided_branch_types:
        for item in target_items:
            if str(item.get("type", "")) == "actions":
                continue
            target_id = str(item.get("id", ""))
            branch_steps = [dict(step) for step in steps if target_id in list(step.get("attached_targets", [])) or (not list(step.get("attached_targets", [])) and str(step.get("kind", "")) in {"autonomy_gate", "browser_status"})]
            if branch_steps:
                add(_clone_plan(primary, branch_steps, branch_id=f"single_target_{target_id}", source="target_specific_branch", note=f"Single-target branch keeps only steps attached to {target_id}.", memory_mode="balanced"), memory_ctx=memory_context, memory_mode="balanced")

    if re.search(r"\brecover\b|\brecovery\b", request_lowered) and re.search(r"\bself repair\b", request_lowered):
        for kind in ("recover", "self_repair"):
            branch_steps = [
                dict(step)
                for step in steps
                if str(step.get("kind", "")) not in _HIGH_RISK_REMEDIATION_KINDS or str(step.get("kind", "")) == kind
            ]
            if not any(str(step.get("kind", "")) == kind for step in branch_steps):
                branch_steps.insert(
                    0,
                    make_step(
                        kind,
                        "runtime",
                        subgoal_id=kind,
                        route_confidence=max(float(primary.get("intent_confidence", 0.6) or 0.6), 0.8),
                        source_of_route="single_remediation_regeneration",
                        justification=f"Single remediation branch rebuilt for explicit {kind} request.",
                    ),
                )
            add(_clone_plan(primary, branch_steps, branch_id=f"single_{kind}", source="single_remediation_regeneration", note=f"Single remediation branch keeping only {kind}.", preferred=(kind == "recover"), memory_mode="balanced"), memory_ctx=memory_context, memory_mode="balanced")

    if (ambiguous_request or float(primary.get("planner_confidence", 1.0) or 1.0) < 0.55 or safe_strategy or guided_strategy == "conservative" or "observation_only" in guided_branch_types) and not explicit_mutation:
        observe_only = [make_step("observe", request_text, subgoal_id="observe", route_confidence=max(0.35, float(primary.get("planner_confidence", 0.5)) - 0.2), source_of_route="ambiguity_observe_only")]
        add(_clone_plan(primary, observe_only, branch_id="observation_only", source="ambiguity_observation_branch", note="Observation-only branch reserved for high-ambiguity requests.", memory_mode="disabled"), memory_ctx=memory_free_context, memory_mode="disabled")

    derivation = derive_interpretations(cwd, request_text, primary, candidates, desired_count=max(16, len(candidates) + 6))
    derivation_scores = {str(item.get("source_branch_id", "")): float(item.get("survival_score", 0.0) or 0.0) for item in list(derivation.get("top_survivors", []))}
    for candidate in candidates:
        branch_id = str((candidate.get("branch") or {}).get("id", ""))
        candidate["derivation_survival_score"] = float(derivation_scores.get(branch_id, 0.0) or 0.0)
    candidates.sort(
        key=lambda candidate: (
            -float(candidate.get("derivation_survival_score", 0.0) or 0.0),
            -float(dict(candidate.get("goal_alignment") or {}).get("score", 0.0) or 0.0),
            -float(dict(candidate.get("survivor_history_prior") or {}).get("score", 0.0) or 0.0),
            -float(candidate.get("route_variant_history_bias", 0.0) or 0.0),
            -float(candidate.get("planner_confidence", 0.0) or 0.0),
            -float(dict(candidate.get("target_coverage") or {}).get("coverage_ratio", 0.0) or 0.0),
        )
    )

    return {
        "ok": True,
        "planner_version": PLANNER_VERSION,
        "request": request_text,
        "intent": dict(primary.get("intent", {})),
        "memory_context": _memory_context_summary(memory_context, mode="balanced"),
        "candidate_count": len(candidates),
        "rejected_candidate_count": len(rejected_candidates),
        "candidates": candidates,
        "rejected_candidates": rejected_candidates,
        "self_derivation": derivation,
        "survivor_guidance": survivor_guidance,
        "survivor_strategy_guidance": strategy_guidance,
    }


def build_plan(request: str, cwd: str = ".", *, memory_mode: str = "balanced", record_snapshot: bool = True) -> dict:
    text = _normalize_text(request)
    lowered = text.lower()
    targets = extract_request_targets(text)
    code_mutation_requested = bool((targets.get("files") or targets.get("file_ranges"))) and any(
        token in lowered for token in ("replace", "edit", "update", "modify", "refactor", "write", "change", "patch")
    )
    code_workbench_context = code_workbench_status(
        cwd,
        requested_files=[item.get("value") for item in list(targets.get("files", []))],
        file_ranges=[item.get("value") for item in list(targets.get("file_ranges", []))],
        requested_mutation=code_mutation_requested,
        request_text=text,
    )
    read_only_request = _request_is_read_only(lowered)
    world_model_context = _planner_world_model_context(cwd)
    memory_context = build_memory_context(cwd, text, extract_intent(text))
    route_history_bias = _route_history_bias(cwd)
    route_variant_bias_map = _route_variant_history_bias(cwd)
    request_decomposition = _split_subgoals(text)
    reasoning_trace = analyze_goal_structure(text, request_decomposition, targets)
    semantic_interpretations = generate_semantic_interpretations(text, request_decomposition, targets)
    semantic_frame = dict(semantic_interpretations[0]) if semantic_interpretations else {}
    semantic_abstraction = semantic_abstraction_profile(text, targets, request_decomposition)
    resolved = _resolve_intents(text, targets, memory_context, decomposition=request_decomposition, memory_mode=memory_mode, route_history_bias=route_history_bias)
    intent = dict(resolved["structured_intent"])
    intent["intent"] = str(resolved["primary_intent"])
    intent["primary_intent"] = str(resolved["primary_intent"])
    intent["secondary_intents"] = list(resolved["secondary_intents"])
    intent["intent_candidates"] = list(resolved["candidates"])
    intent["intent_scores"] = dict(resolved.get("intent_scores", {}))
    intent["route_history_bias"] = dict(resolved.get("route_history_bias", {}))
    ambiguity_flags = list(resolved["ambiguity_flags"])
    conflicting_signals = list(resolved["conflicting_signals"])
    remembered_plan = None
    if str(intent.get("constraints", {}).get("resume", "")).lower() == "true":
        remembered_plan = lookup(cwd, intent["intent"])

    composed = compose_primary_steps(
        text,
        lowered,
        targets,
        resolved,
        remembered_plan=remembered_plan,
        initial_ambiguity_flags=ambiguity_flags,
    )
    steps = list(composed.get("steps", []))
    ambiguity_flags = list(composed.get("ambiguity_flags", ambiguity_flags))

    steps = _dedupe_steps(steps)
    parsed_code_instruction = parse_code_instruction(text) if code_mutation_requested else {"ok": False}
    if any(str(step.get("kind", "")) == "code_change" for step in steps):
        for step in steps:
            if str(step.get("kind", "")) != "code_change":
                continue
            target = dict(step.get("target") or {})
            target["code_workbench"] = dict(code_workbench_context)
            if not dict(target.get("instruction") or {}):
                target["instruction"] = dict(parsed_code_instruction)
            step["target"] = target
    remediation_kinds = [str(step.get("kind", "")) for step in steps if str(step.get("kind", "")) in _HIGH_RISK_REMEDIATION_KINDS]
    branch_id = "primary"
    if len(set(remediation_kinds)) > 1:
        preferred = "recover" if "recover" in remediation_kinds else remediation_kinds[0]
        ambiguity_flags.append("conflicting_remediation_intents")
        conflicting_signals.append("recover_and_self_repair_overlap")
        steps = [dict(step) for step in steps if str(step.get("kind", "")) not in _HIGH_RISK_REMEDIATION_KINDS or str(step.get("kind", "")) == preferred]
        branch_id = f"single_{preferred}"
    if read_only_request and not any(token in lowered for token in MUTATION_TOKENS):
        filtered_steps = [dict(step) for step in steps if not step_allows_mutation(str(step.get("kind", "")))]
        if filtered_steps != steps:
            ambiguity_flags.append("mutating_subgoal_removed_from_read_only_primary")
            steps = filtered_steps
    if not steps:
        steps.append(make_step("observe", text, subgoal_id="observe", route_confidence=0.5, source_of_route="fallback_observe"))
    memory_summary = _memory_context_summary(memory_context, mode=memory_mode)
    steps, request_decomposition = _attach_step_decomposition(steps, request_decomposition, targets)
    steps = _annotate_step_causality(steps)
    survivor_primary = _maybe_apply_survivor_guidance_to_primary(
        cwd,
        steps,
        request_decomposition,
        targets,
        attached=True,
        reasoning_trace=reasoning_trace,
        read_only_request=read_only_request,
        intent_confidence=float(resolved["primary_confidence"]),
        ambiguity_flags=ambiguity_flags,
        conflicting_signals=conflicting_signals,
        route_history_bias=dict(resolved.get("route_history_bias", {})),
        memory_strength=str(memory_summary.get("memory_strength", "none")),
    )
    survivor_guidance = dict(survivor_primary.get("guidance") or {})
    survivor_guidance_applied = bool(survivor_primary.get("applied", False))
    survivor_guidance_pattern = str(survivor_primary.get("applied_pattern", ""))
    if survivor_guidance_applied:
        steps = _annotate_step_reasoning(_annotate_step_causality([dict(step) for step in list(survivor_primary.get("steps", []))]))
        ambiguity_flags.append("survivor_guided_primary")
    planner_precheck = simulate_plan_conflicts(steps, request_decomposition, targets, read_only_request=read_only_request)
    if planner_precheck.get("has_conflict", False):
        ambiguity_flags.append("planner_precheck_conflict")
        ambiguity_flags.extend(str(item.get("code", "")) for item in list(planner_precheck.get("issues", [])) if str(item.get("code", "")))
        if any(str(item.get("severity", "")) == "high" for item in list(planner_precheck.get("issues", []))):
            conflicting_signals.append("planner_precheck_high_conflict")
    steps, precondition_flags = _annotate_step_contracts(steps)
    steps = _annotate_step_reasoning(steps)
    ambiguity_flags.extend(precondition_flags)
    world_model_blockers = {
        domain
        for domain in list(world_model_context.get("blocked_domains", []))
        if domain in {"approvals", "continuity", "runtime"}
    }
    if world_model_blockers and any(step_allows_mutation(str(step.get("kind", ""))) for step in steps):
        ambiguity_flags.append("world_model_blocked_mutation_context")
        conflicting_signals.extend(f"world_model_{domain}_blocked" for domain in sorted(world_model_blockers))
    coverage = _coverage_for_steps(targets, steps)
    if coverage["unbound_targets"]:
        ambiguity_flags.append("unbound_explicit_targets")
        ambiguity_flags.append("dropped_target")
    planner_confidence = _planner_confidence(float(resolved["primary_confidence"]), float(coverage["coverage_ratio"]), len(set(ambiguity_flags)), len(set(conflicting_signals)), len(list(coverage["unbound_targets"])))
    planner_confidence = max(
        0.0,
        round(
            planner_confidence
            - float(planner_precheck.get("confidence_adjustment", 0.0) or 0.0)
            - (0.08 if str(memory_summary.get("memory_strength", "")) == "conflicting" else 0.0)
            - min(0.08, _dependency_depth(request_decomposition) * 0.02)
            - (0.12 if "world_model_blocked_mutation_context" in ambiguity_flags else 0.0),
            3,
        ),
    )
    conservative_fallback_active = False
    if planner_confidence < 0.45 and any(step_allows_mutation(str(step.get("kind", ""))) for step in steps):
        conservative_steps = [dict(step) for step in steps if not step_allows_mutation(str(step.get("kind", "")))]
        if not conservative_steps:
            conservative_steps = [make_step("observe", text, subgoal_id="observe", route_confidence=0.4, source_of_route="low_confidence_conservative_fallback")]
        steps, _ = _annotate_step_contracts(_annotate_step_causality(conservative_steps))
        steps = _annotate_step_reasoning(steps)
        ambiguity_flags.append("low_confidence_conservative_primary")
        branch_id = "conservative_primary"
        conservative_fallback_active = True
        survivor_guidance_applied = False
        survivor_guidance_pattern = ""
        coverage = _coverage_for_steps(targets, steps)
        planner_confidence = _planner_confidence(float(resolved["primary_confidence"]), float(coverage["coverage_ratio"]), len(set(ambiguity_flags)), len(set(conflicting_signals)), len(list(coverage["unbound_targets"])))
    risk_level = _plan_risk_level(steps)
    plan = {
        "ok": True,
        "planner_version": PLANNER_VERSION,
        "request": text,
        "intent": intent,
        "intent_scores": dict(resolved.get("intent_scores", {})),
        "route_history_bias": dict(resolved.get("route_history_bias", {})),
        "intent_confidence": float(resolved["primary_confidence"]),
        "planner_confidence": planner_confidence,
        "ambiguity": list(dict.fromkeys(ambiguity_flags)),
        "ambiguity_flags": list(dict.fromkeys(ambiguity_flags)),
        "conflicting_signals": list(dict.fromkeys(conflicting_signals)),
        "dropped_targets": list(coverage["unbound_targets"]),
        "uncovered_targets": list(coverage["unbound_targets"]),
        "read_only_request": read_only_request,
        "targets": targets,
        "request_targets": targets,
        "target_coverage": coverage,
        "target_coverage_valid": not bool(coverage["unbound_targets"]),
        "risk": risk_level,
        "risk_level": risk_level,
        "route_confidence_by_step": {str(index): float(step.get("route_confidence", 0.0) or 0.0) for index, step in enumerate(steps)},
        "steps": steps,
        "request_decomposition": request_decomposition,
        "branch_reason": "low_confidence_conservative_fallback" if conservative_fallback_active else "survivor_guided_primary" if survivor_guidance_applied else "weighted_primary_route",
        "branch": {
            "id": branch_id,
            "source": "weighted_intent_resolution_survivor_guided" if survivor_guidance_applied else "weighted_intent_resolution",
            "note": (
                f"Primary branch shaped by survivor-guided history pattern `{survivor_guidance_pattern}` after safe precheck."
                if survivor_guidance_applied
                else "Primary branch built from weighted intent resolution and target-aware step composition."
                if not conservative_fallback_active
                else "Primary branch downgraded into conservative mode because planner confidence was too low for mutation."
            ),
            "preferred": True,
            "memory_mode": memory_mode,
        },
        "conservative_fallback_active": conservative_fallback_active,
        "reasoning_trace": reasoning_trace,
        "planner_precheck": planner_precheck,
        "survivor_guidance": survivor_guidance,
        "survivor_guidance_applied": survivor_guidance_applied,
        "survivor_guidance_pattern": survivor_guidance_pattern,
        "semantic_interpretations": semantic_interpretations,
        "semantic_frame": semantic_frame,
        "semantic_abstraction": semantic_abstraction,
        "world_model_context": world_model_context,
        "code_workbench_context": code_workbench_context,
    }
    plan["memory_context"] = memory_summary
    plan["memory_reliability"] = str((plan["memory_context"] or {}).get("memory_strength", "none"))
    plan["semantic_goal"] = str(resolved.get("semantic_goal", semantic_frame.get("goal", "")))
    plan["semantic_roles"] = list(resolved.get("semantic_roles", semantic_frame.get("structure", [])))
    plan["evidence"] = score_branch_support(plan, memory_context if memory_mode != "disabled" else _strip_memory_context(memory_context))
    plan["memory_dependency"] = float(plan["evidence"].get("memory_weight", 0.0) or 0.0)
    plan["survivor_history_prior"] = survivor_history_score(cwd, plan)
    plan["survivor_strategy_guidance"] = survivor_strategy_guidance(cwd, plan)
    plan["smart_planner"] = derive_smart_planner_profile(
        text,
        list(plan.get("steps", [])),
        list(plan.get("request_decomposition", [])),
        dict(plan.get("request_targets", {})),
        planner_confidence=float(plan.get("planner_confidence", 0.0) or 0.0),
        risk_level=str(plan.get("risk_level", "low")),
        ambiguity_flags=list(plan.get("ambiguity_flags", [])),
        route_history_bias=dict(plan.get("route_history_bias", {})),
        reasoning_trace=reasoning_trace,
        precheck=planner_precheck,
        survivor_strategy_guidance=dict(plan.get("survivor_strategy_guidance", {})),
    )
    plan["plan_simulation"] = simulate_plan(
        list(plan.get("steps", [])),
        list(plan.get("request_decomposition", [])),
        dict(plan.get("request_targets", {})),
        planner_confidence=float(plan.get("planner_confidence", 0.0) or 0.0),
        risk_level=str(plan.get("risk_level", "low")),
        ambiguity_flags=list(plan.get("ambiguity_flags", [])),
        route_history_bias=dict(plan.get("route_history_bias", {})),
        precheck=planner_precheck,
        memory_strength=str(plan.get("memory_reliability", "none")),
    )
    plan["predicted_risk"] = str((plan.get("plan_simulation") or {}).get("predicted_risk", plan.get("risk_level", "low")))
    plan["expected_success"] = float((plan.get("plan_simulation") or {}).get("expected_success", plan.get("planner_confidence", 0.0)) or 0.0)
    plan["self_critique"] = critique_plan(
        planner_confidence=float(plan.get("planner_confidence", 0.0) or 0.0),
        coverage_ratio=float(dict(plan.get("target_coverage") or {}).get("coverage_ratio", 0.0) or 0.0),
        simulation=dict(plan.get("plan_simulation") or {}),
        precheck=planner_precheck,
        memory_strength=str(plan.get("memory_reliability", "none")),
    )
    if bool(dict(plan.get("self_critique") or {}).get("downgrade_recommended", False)):
        plan["smart_planner"]["planner_mode"] = "safe"
        plan["smart_planner"]["strategy_mode"] = "safe"
        plan["smart_planner"]["reasons"] = list(
            dict.fromkeys(list(plan["smart_planner"].get("reasons", [])) + ["self_critique_safe_downgrade"])
        )
    plan["execution_mode"] = str((plan.get("smart_planner") or {}).get("planner_mode", "normal"))
    plan["phases"] = phase_plan(list(plan.get("steps", [])))
    plan["route_variant"] = _planner_route_variant(plan)
    plan["route_surface"] = str(plan["route_variant"])
    plan["route_variant_history_bias"] = round(float(route_variant_bias_map.get(str(plan["route_variant"]), 0.0) or 0.0), 3)
    plan["branch"]["route_variant"] = str(plan["route_variant"])
    plan["branch"]["route_surface"] = str(plan["route_surface"])
    plan["goal_alignment"] = _goal_alignment_score(text, plan, world_model_context)
    if any(str(step.get("kind", "")) == "code_change" for step in list(plan.get("steps", []))):
        plan["decision_governor"] = governor_decide(
            cwd,
            world_model=overlay_world_model_with_codebase(world_model_status(cwd), dict(code_workbench_context)),
        )
    plan["explanation"] = explain_plan(
        intent_candidate=dict((resolved.get("candidates") or [{}])[0]),
        smart_profile=dict(plan.get("smart_planner", {})),
        precheck=planner_precheck,
        risk_level=risk_level,
        branch_reason=str(plan.get("branch_reason", "")),
        simulation=dict(plan.get("plan_simulation") or {}),
        critique=dict(plan.get("self_critique") or {}),
        planner_confidence=float(plan.get("planner_confidence", 0.0) or 0.0),
    )
    if memory_mode == "balanced" and record_snapshot:
        record_smart_planner_snapshot(cwd, dict(plan["smart_planner"]))
    return plan


def record_planner_outcome(cwd: str, request: str, branch_selection: dict[str, Any] | None, run: dict) -> dict[str, Any]:
    data = _load_feedback(cwd)
    history = list(data.get("history", []))
    selected_plan = dict((branch_selection or {}).get("selected_plan") or run.get("plan") or {})
    contradiction_gate = dict(run.get("contradiction_gate", {}))
    results = list(run.get("results", []))
    route = str(((selected_plan.get("intent") or {}).get("primary_intent") or (selected_plan.get("intent") or {}).get("intent") or "observe"))
    route_variant = _planner_route_variant(selected_plan)
    approval_required_count = sum(1 for item in results if str(item.get("reason", "")) == "approval_required")
    target_coverage = dict(selected_plan.get("target_coverage") or {})
    entry = {
        "time_utc": _utc_now(),
        "request": _normalize_text(request),
        "feedback_schema_version": PLANNER_FEEDBACK_SCHEMA_VERSION,
        "planner_version": str(selected_plan.get("planner_version", PLANNER_VERSION)),
        "route": route,
        "route_variant": route_variant,
        "route_surface": route_variant,
        "branch_id": str((selected_plan.get("branch") or {}).get("id", "primary")),
        "branch_reason": str(selected_plan.get("branch_reason", "")),
        "planner_confidence": float(selected_plan.get("planner_confidence", 0.0) or 0.0),
        "coverage_ratio": float(target_coverage.get("coverage_ratio", 0.0) or 0.0),
        "ok": bool(run.get("ok", False)),
        "contradiction_hold": str(contradiction_gate.get("decision", "")) == "hold",
        "target_drop_count": len(list(target_coverage.get("unbound_targets", []))),
        "approval_required_count": approval_required_count,
        "approval_required_surprise": approval_required_count > 0 and not any(bool(step.get("requires_approval_possible", False)) for step in list(selected_plan.get("steps", []))),
        "rerouted_after_failure": bool((branch_selection or {}).get("discarded_count", 0)),
    }
    history.append(entry)
    data["history"] = history[-200:]
    data = _summarize_feedback(data)
    _save_feedback(cwd, data)
    return {"ok": True, "path": str(_feedback_path(cwd)), "entry": entry, "summary": dict(data.get("summary", {}))}


def planner_feedback_status(cwd: str) -> dict[str, Any]:
    data = _summarize_feedback(_load_feedback(cwd))
    return {"ok": True, "path": str(_feedback_path(cwd)), **data}


def smart_planner_status(cwd: str) -> dict[str, Any]:
    return _smart_planner_status(cwd)


def self_derivation_status(cwd: str) -> dict[str, Any]:
    return _self_derivation_status(cwd)


def self_derivation_assess(request: str, cwd: str = ".") -> dict[str, Any]:
    plan = build_plan(request, cwd, record_snapshot=False)
    bundle = build_candidate_plans(request, cwd, base_plan=plan)
    return {
        "ok": True,
        "request": str(plan.get("request", request)),
        "planner_version": str(plan.get("planner_version", PLANNER_VERSION)),
        "recommended_branch_id": str(dict(bundle.get("self_derivation", {})).get("recommended_branch_id", "")),
        "candidate_count": int(bundle.get("candidate_count", 0) or 0),
        "self_derivation": dict(bundle.get("self_derivation", {})),
        "smart_planner": dict(plan.get("smart_planner", {})),
    }


def self_derivation_revalidate(cwd: str, *, strategy: str = "", limit: int = 3) -> dict[str, Any]:
    return _self_derivation_revalidate(cwd, strategy=strategy, limit=limit)


def smart_planner_assess(request: str, cwd: str = ".") -> dict[str, Any]:
    plan = build_plan(request, cwd)
    bundle = build_candidate_plans(request, cwd, base_plan=plan)
    return {
        "ok": True,
        "request": str(plan.get("request", request)),
        "planner_version": str(plan.get("planner_version", PLANNER_VERSION)),
        "intent": dict(plan.get("intent", {})),
        "planner_confidence": float(plan.get("planner_confidence", 0.0) or 0.0),
        "risk_level": str(plan.get("risk_level", "low")),
        "predicted_risk": str(plan.get("predicted_risk", plan.get("risk_level", "low"))),
        "expected_success": float(plan.get("expected_success", plan.get("planner_confidence", 0.0)) or 0.0),
        "smart_planner": dict(plan.get("smart_planner", {})),
        "plan_simulation": dict(plan.get("plan_simulation", {})),
        "self_critique": dict(plan.get("self_critique", {})),
        "self_derivation": dict(bundle.get("self_derivation", {})),
        "explanation": dict(plan.get("explanation", {})),
    }
