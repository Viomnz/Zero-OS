from __future__ import annotations

import json
import re
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from zero_os.memory_tier_filter import build_memory_context, score_branch_support
from zero_os.playbook_memory import lookup
from zero_os.smart_planner import derive_smart_planner_profile, record_smart_planner_snapshot, smart_planner_status as _smart_planner_status
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


PLANNER_VERSION = "2026.03.22"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _feedback_path(cwd: str) -> Path:
    path = Path(cwd).resolve() / ".zero_os" / "assistant" / "planner_feedback.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _load_feedback(cwd: str) -> dict[str, Any]:
    path = _feedback_path(cwd)
    if not path.exists():
        return {"schema_version": 1, "history": []}
    try:
        raw = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {"schema_version": 1, "history": []}
    if not isinstance(raw, dict):
        return {"schema_version": 1, "history": []}
    raw.setdefault("schema_version", 1)
    raw.setdefault("history", [])
    return raw


def _save_feedback(cwd: str, payload: dict[str, Any]) -> None:
    _feedback_path(cwd).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _route_history_bias(cwd: str) -> dict[str, float]:
    summary = dict(_load_feedback(cwd).get("summary") or {})
    routes = dict(summary.get("routes") or {})
    bias: dict[str, float] = {}
    for route_name, metrics in routes.items():
        count = int(metrics.get("count", 0) or 0)
        if count < 2:
            continue
        success = float(metrics.get("successful_completion_rate", 0.0) or 0.0)
        hold = float(metrics.get("contradiction_hold_rate", 0.0) or 0.0)
        failure = float(metrics.get("execution_failure_rate", 0.0) or 0.0)
        target_drop = float(metrics.get("target_drop_rate", 0.0) or 0.0)
        reroute = float(metrics.get("reroute_after_failure_rate", 0.0) or 0.0)
        approval_surprise = float(metrics.get("approval_required_surprise_rate", 0.0) or 0.0)
        quality = success - (hold * 0.45) - (failure * 0.35) - (target_drop * 0.25) - (reroute * 0.15) - (approval_surprise * 0.1)
        value = round(max(-0.18, min(0.18, (quality - 0.55) * 0.3)), 3)
        if abs(value) >= 0.01:
            bias[str(route_name)] = value
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
        else:
            updated["decomposition_subgoal_id"] = str(updated.get("subgoal_id", ""))
            updated["decomposition_order"] = original_index
            updated["decomposition_dependency_kind"] = "unmatched"
            updated["decomposition_depends_on"] = []
            updated["decomposition_blocking"] = False
            updated["decomposition_conditional"] = False
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
    normalized_steps = sorted(
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
    )
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


def _attach_branch_support(plan: dict, memory_context: dict, *, memory_mode: str) -> dict:
    enriched = deepcopy(plan)
    enriched["risk_level"] = _plan_risk_level(list(enriched.get("steps", [])))
    enriched["risk"] = enriched["risk_level"]
    enriched["memory_context"] = _memory_context_summary(memory_context, mode=memory_mode)
    enriched["evidence"] = score_branch_support(enriched, memory_context)
    enriched["memory_dependency"] = float(enriched["evidence"].get("memory_weight", 0.0) or 0.0)
    enriched["target_coverage"] = _coverage_for_steps(dict(enriched.get("request_targets", {})), list(enriched.get("steps", [])))
    enriched["dropped_targets"] = list(enriched["target_coverage"].get("unbound_targets", []))
    enriched["route_confidence_by_step"] = {
        str(index): float(step.get("route_confidence", 0.0) or 0.0)
        for index, step in enumerate(list(enriched.get("steps", [])))
    }
    return enriched


def build_candidate_plans(request: str, cwd: str = ".", base_plan: dict | None = None) -> dict:
    primary = deepcopy(base_plan) if base_plan else build_plan(request, cwd, memory_mode="balanced")
    request_text = str(primary.get("request", _normalize_text(request)))
    memory_context = build_memory_context(cwd, request_text, dict(primary.get("intent", {})))
    memory_free_context = _strip_memory_context(memory_context)
    candidates: list[dict] = []
    exact_seen: set[str] = set()
    semantic_seen: dict[str, int] = {}

    def add(plan: dict, *, memory_ctx: dict, memory_mode: str) -> None:
        attached = _attach_branch_support(plan, memory_ctx, memory_mode=memory_mode)
        coverage = dict(attached.get("target_coverage", {}))
        if not attached.get("planner_confidence"):
            attached["planner_confidence"] = _planner_confidence(
                float(attached.get("intent_confidence", 0.5) or 0.5),
                float(coverage.get("coverage_ratio", 0.0) or 0.0),
                len(list(attached.get("ambiguity_flags", []))),
                len(list(attached.get("conflicting_signals", []))),
                len(list(coverage.get("unbound_targets", []))),
            )
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
    verification_first = sorted(
        [dict(step) for step in steps],
        key=lambda step: (
            0 if str(step.get("kind", "")) in _VERIFICATION_PRIORITY_KINDS else 1,
            0 if str(step.get("risk_level", "")) == "low" else 1,
            -float(step.get("route_confidence", 0.0) or 0.0),
        ),
    )
    add(_clone_plan(primary, verification_first, branch_id="verification_first", source="verification_first", note="Verification-first branch reorders observation and verification before mutation.", memory_mode="balanced"), memory_ctx=memory_context, memory_mode="balanced")

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
    if bool(primary.get("read_only_request")) or (ambiguous_request and not explicit_mutation):
        add(_clone_plan(primary, minimal_safe, branch_id="minimal_safe", source="minimal_safe_branch", note="Minimal-safe branch keeps one low-risk verification step per subgoal.", memory_mode="balanced"), memory_ctx=memory_context, memory_mode="balanced")

    if bool(primary.get("read_only_request")) or (ambiguous_request and not explicit_mutation) or any(str(step.get("risk_level", "")) == "high" for step in steps):
        conservative = [dict(step) for step in steps if not step_allows_mutation(str(step.get("kind", "")))]
        if conservative:
            add(_clone_plan(primary, conservative, branch_id="conservative_execution", source="risk_conservative_branch", note="Conservative execution branch drops mutating steps while preserving observation coverage.", memory_mode="balanced"), memory_ctx=memory_context, memory_mode="balanced")

    evidence_first = sorted([dict(step) for step in steps], key=lambda step: (0 if str(step.get("verification_mode", "")) == "observe" else 1, -float(step.get("route_confidence", 0.0) or 0.0), 0 if str(step.get("risk_level", "")) == "low" else 1))
    add(_clone_plan(primary, evidence_first, branch_id="evidence_first", source="evidence_first_branch", note="Evidence-first branch prioritizes strongly-supported low-risk steps before other work.", memory_mode="balanced"), memory_ctx=memory_context, memory_mode="balanced")

    target_items = list((primary.get("request_targets") or {}).get("items", []))
    if len(target_items) > 1:
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

    if (ambiguous_request or float(primary.get("planner_confidence", 1.0) or 1.0) < 0.55) and not explicit_mutation:
        observe_only = [make_step("observe", request_text, subgoal_id="observe", route_confidence=max(0.35, float(primary.get("planner_confidence", 0.5)) - 0.2), source_of_route="ambiguity_observe_only")]
        add(_clone_plan(primary, observe_only, branch_id="observation_only", source="ambiguity_observation_branch", note="Observation-only branch reserved for high-ambiguity requests.", memory_mode="disabled"), memory_ctx=memory_free_context, memory_mode="disabled")

    return {
        "ok": True,
        "planner_version": PLANNER_VERSION,
        "request": request_text,
        "intent": dict(primary.get("intent", {})),
        "memory_context": _memory_context_summary(memory_context, mode="balanced"),
        "candidate_count": len(candidates),
        "candidates": candidates,
    }


def build_plan(request: str, cwd: str = ".", *, memory_mode: str = "balanced") -> dict:
    text = _normalize_text(request)
    lowered = text.lower()
    targets = extract_request_targets(text)
    read_only_request = _request_is_read_only(lowered)
    memory_context = build_memory_context(cwd, text, extract_intent(text))
    route_history_bias = _route_history_bias(cwd)
    resolved = _resolve_intents(text, targets, memory_context, memory_mode=memory_mode, route_history_bias=route_history_bias)
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
    request_decomposition = _split_subgoals(text)

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
    steps, request_decomposition = _attach_step_decomposition(steps, request_decomposition, targets)
    steps, precondition_flags = _annotate_step_contracts(steps)
    ambiguity_flags.extend(precondition_flags)
    coverage = _coverage_for_steps(targets, steps)
    if coverage["unbound_targets"]:
        ambiguity_flags.append("unbound_explicit_targets")
        ambiguity_flags.append("dropped_target")
    planner_confidence = _planner_confidence(float(resolved["primary_confidence"]), float(coverage["coverage_ratio"]), len(set(ambiguity_flags)), len(set(conflicting_signals)), len(list(coverage["unbound_targets"])))
    conservative_fallback_active = False
    if planner_confidence < 0.45 and any(step_allows_mutation(str(step.get("kind", ""))) for step in steps):
        conservative_steps = [dict(step) for step in steps if not step_allows_mutation(str(step.get("kind", "")))]
        if not conservative_steps:
            conservative_steps = [make_step("observe", text, subgoal_id="observe", route_confidence=0.4, source_of_route="low_confidence_conservative_fallback")]
        steps, _ = _annotate_step_contracts(conservative_steps)
        ambiguity_flags.append("low_confidence_conservative_primary")
        branch_id = "conservative_primary"
        conservative_fallback_active = True
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
        "branch_reason": "low_confidence_conservative_fallback" if conservative_fallback_active else "weighted_primary_route",
        "branch": {"id": branch_id, "source": "weighted_intent_resolution", "note": "Primary branch built from weighted intent resolution and target-aware step composition." if not conservative_fallback_active else "Primary branch downgraded into conservative mode because planner confidence was too low for mutation.", "preferred": True, "memory_mode": memory_mode},
        "conservative_fallback_active": conservative_fallback_active,
    }
    plan["memory_context"] = _memory_context_summary(memory_context, mode=memory_mode)
    plan["memory_reliability"] = str((plan["memory_context"] or {}).get("memory_strength", "none"))
    plan["evidence"] = score_branch_support(plan, memory_context if memory_mode != "disabled" else _strip_memory_context(memory_context))
    plan["memory_dependency"] = float(plan["evidence"].get("memory_weight", 0.0) or 0.0)
    plan["smart_planner"] = derive_smart_planner_profile(
        text,
        list(plan.get("steps", [])),
        list(plan.get("request_decomposition", [])),
        dict(plan.get("request_targets", {})),
        planner_confidence=float(plan.get("planner_confidence", 0.0) or 0.0),
        risk_level=str(plan.get("risk_level", "low")),
        ambiguity_flags=list(plan.get("ambiguity_flags", [])),
        route_history_bias=dict(plan.get("route_history_bias", {})),
    )
    if memory_mode == "balanced":
        record_smart_planner_snapshot(cwd, dict(plan["smart_planner"]))
    return plan


def record_planner_outcome(cwd: str, request: str, branch_selection: dict[str, Any] | None, run: dict) -> dict[str, Any]:
    data = _load_feedback(cwd)
    history = list(data.get("history", []))
    selected_plan = dict((branch_selection or {}).get("selected_plan") or run.get("plan") or {})
    contradiction_gate = dict(run.get("contradiction_gate", {}))
    results = list(run.get("results", []))
    route = str(((selected_plan.get("intent") or {}).get("primary_intent") or (selected_plan.get("intent") or {}).get("intent") or "observe"))
    approval_required_count = sum(1 for item in results if str(item.get("reason", "")) == "approval_required")
    target_coverage = dict(selected_plan.get("target_coverage") or {})
    entry = {
        "time_utc": _utc_now(),
        "request": _normalize_text(request),
        "planner_version": str(selected_plan.get("planner_version", PLANNER_VERSION)),
        "route": route,
        "branch_id": str((selected_plan.get("branch") or {}).get("id", "primary")),
        "branch_reason": str(selected_plan.get("branch_reason", "")),
        "planner_confidence": float(selected_plan.get("planner_confidence", 0.0) or 0.0),
        "ok": bool(run.get("ok", False)),
        "contradiction_hold": str(contradiction_gate.get("decision", "")) == "hold",
        "target_drop_count": len(list(target_coverage.get("unbound_targets", []))),
        "approval_required_count": approval_required_count,
        "approval_required_surprise": approval_required_count > 0 and not any(bool(step.get("requires_approval_possible", False)) for step in list(selected_plan.get("steps", []))),
        "rerouted_after_failure": bool((branch_selection or {}).get("discarded_count", 0)),
    }
    history.append(entry)
    data["history"] = history[-200:]
    routes_summary: dict[str, Any] = {}
    route_names = sorted({str(item.get("route", "")) for item in data["history"] if str(item.get("route", ""))})
    for route_name in route_names:
        route_entries = [item for item in data["history"] if str(item.get("route", "")) == route_name]
        total = max(1, len(route_entries))
        routes_summary[route_name] = {
            "count": len(route_entries),
            "contradiction_hold_rate": round(sum(1 for item in route_entries if item.get("contradiction_hold")) / total, 3),
            "execution_failure_rate": round(sum(1 for item in route_entries if not item.get("ok", False)) / total, 3),
            "approval_required_surprise_rate": round(sum(1 for item in route_entries if item.get("approval_required_surprise")) / total, 3),
            "target_drop_rate": round(sum(int(item.get("target_drop_count", 0)) for item in route_entries) / total, 3),
            "successful_completion_rate": round(sum(1 for item in route_entries if item.get("ok", False)) / total, 3),
            "reroute_after_failure_rate": round(sum(1 for item in route_entries if item.get("rerouted_after_failure")) / total, 3),
        }
    data["summary"] = {
        "history_count": len(data["history"]),
        "routes": routes_summary,
    }
    _save_feedback(cwd, data)
    return {"ok": True, "path": str(_feedback_path(cwd)), "entry": entry, "summary": dict(data.get("summary", {}))}


def planner_feedback_status(cwd: str) -> dict[str, Any]:
    data = _load_feedback(cwd)
    return {"ok": True, "path": str(_feedback_path(cwd)), **data}


def smart_planner_status(cwd: str) -> dict[str, Any]:
    return _smart_planner_status(cwd)


def smart_planner_assess(request: str, cwd: str = ".") -> dict[str, Any]:
    plan = build_plan(request, cwd)
    return {
        "ok": True,
        "request": str(plan.get("request", request)),
        "planner_version": str(plan.get("planner_version", PLANNER_VERSION)),
        "intent": dict(plan.get("intent", {})),
        "planner_confidence": float(plan.get("planner_confidence", 0.0) or 0.0),
        "risk_level": str(plan.get("risk_level", "low")),
        "smart_planner": dict(plan.get("smart_planner", {})),
    }
