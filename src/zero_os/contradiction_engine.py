from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


_MUTATING_STEP_KINDS = {
    "browser_action",
    "browser_open",
    "cloud_deploy",
    "recover",
    "self_repair",
    "store_install",
}
_STATUS_INTENTS = {"planning", "reasoning", "status", "tools"}
_HIGH_RISK_REMEDIATION_KINDS = {"recover", "self_repair"}
_PRIORITY_ORDER = ("truth", "consistency", "goal_fit", "consequence", "efficiency", "style")
_CHECKS = ("self_model", "goal", "context", "workflow", "evolution", "evidence", "consequence")
_KNOWN_STEP_KINDS = {
    "api_request",
    "api_workflow",
    "autonomy_gate",
    "browser_action",
    "browser_dom_inspect",
    "browser_open",
    "browser_status",
    "cloud_deploy",
    "cloud_target_set",
    "controller_registry",
    "contradiction_engine",
    "pressure_harness",
    "evolution_auto_run",
    "source_evolution_auto_run",
    "flow_monitor",
    "github_connect",
    "github_issue_act",
    "github_issue_comments",
    "github_issue_plan",
    "github_issue_read",
    "github_issue_reply_draft",
    "github_issue_reply_post",
    "github_issues",
    "github_pr_act",
    "github_pr_comments",
    "github_pr_plan",
    "github_pr_read",
    "github_pr_reply_draft",
    "github_pr_reply_post",
    "github_prs",
    "highway_dispatch",
    "observe",
    "recover",
    "self_repair",
    "smart_workspace",
    "store_install",
    "store_status",
    "system_status",
    "tool_registry",
    "web_fetch",
    "web_verify",
}
_INTENT_STEP_EXPECTATIONS = {
    "planning": {"controller_registry"},
    "pressure": {"pressure_harness"},
    "reasoning": {"contradiction_engine"},
    "recover": {"recover"},
    "self_repair": {"self_repair"},
    "status": {"observe", "system_status"},
    "store_install": {"store_install"},
    "store_status": {"store_status"},
    "tools": {"tool_registry"},
    "web": {"browser_action", "browser_dom_inspect", "browser_open", "browser_status", "web_fetch", "web_verify"},
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _assistant_dir(cwd: str) -> Path:
    path = Path(cwd).resolve() / ".zero_os" / "assistant"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _path(cwd: str) -> Path:
    return _assistant_dir(cwd) / "contradiction_engine.json"


def _load(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return dict(default)
    try:
        raw = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return dict(default)
    if not isinstance(raw, dict):
        return dict(default)
    merged = dict(default)
    merged.update(raw)
    return merged


def _save(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _default_state() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "enabled": True,
        "priority_order": list(_PRIORITY_ORDER),
        "checks": list(_CHECKS),
        "last_decision": "unknown",
        "last_checked_utc": "",
        "last_contradiction_count": 0,
        "last_request": "",
        "last_plan_intent": "",
        "last_issues": [],
        "last_mode": "",
        "history": [],
    }


def _continuity_signals(cwd: str) -> dict[str, Any]:
    if not cwd:
        return {
            "same_system": True,
            "has_contradiction": False,
            "issues": [],
            "continuity_score": 100.0,
            "policy_memory_event_count": 0,
        }
    from zero_os.self_continuity import zero_ai_self_continuity_status

    continuity = zero_ai_self_continuity_status(cwd)
    continuity_block = dict(continuity.get("continuity") or {})
    contradiction_block = dict(continuity.get("contradiction_detection") or {})
    policy_memory = dict(continuity.get("policy_memory") or {})
    return {
        "same_system": bool(continuity_block.get("same_system", False)),
        "has_contradiction": bool(contradiction_block.get("has_contradiction", False)),
        "issues": list(contradiction_block.get("issues", [])),
        "continuity_score": float(continuity_block.get("continuity_score", 0.0) or 0.0),
        "policy_memory_event_count": int(policy_memory.get("contradiction_event_count", 0) or 0),
    }


def _urls_in_request(request: str) -> list[str]:
    return re.findall(r"https?://\S+", request or "")


def _step_kind_set(plan: dict[str, Any] | None, results: list[dict[str, Any]]) -> set[str]:
    step_kinds = {str(step.get("kind", "")).strip() for step in list((plan or {}).get("steps", []))}
    result_kinds = {str(item.get("kind", "")).strip() for item in results}
    return {kind for kind in step_kinds | result_kinds if kind}


def _claim_node(node_id: str, node_type: str, value: Any, **extra: Any) -> dict[str, Any]:
    payload = {"id": node_id, "type": node_type, "value": value}
    payload.update(extra)
    return payload


def build_claim_graph(request: str, plan: dict[str, Any] | None, results: list[dict[str, Any]]) -> dict[str, Any]:
    intent = dict((plan or {}).get("intent") or {})
    nodes: list[dict[str, Any]] = [
        _claim_node("request", "goal", (request or "").strip()),
        _claim_node("intent", "intent", str(intent.get("intent", "observe"))),
    ]
    edges: list[dict[str, str]] = [{"source": "request", "target": "intent", "relation": "implies"}]

    branch = dict((plan or {}).get("branch") or {})
    if branch:
        nodes.append(_claim_node("branch", "branch", str(branch.get("source", "primary")), note=str(branch.get("note", ""))))
        edges.append({"source": "intent", "target": "branch", "relation": "materializes_as"})

    evidence = dict((plan or {}).get("evidence") or {})
    if evidence:
        nodes.append(
            _claim_node(
                "evidence",
                "evidence",
                float(evidence.get("total_weight", 0.0) or 0.0),
                memory_weight=float(evidence.get("memory_weight", 0.0) or 0.0),
                core_law_weight=float(evidence.get("core_law_weight", 0.0) or 0.0),
            )
        )
        edges.append({"source": "intent", "target": "evidence", "relation": "supported_by"})

    for index, goal in enumerate(list(intent.get("goals", []))):
        node_id = f"goal_{index}"
        nodes.append(_claim_node(node_id, "goal", str(goal)))
        edges.append({"source": "request", "target": node_id, "relation": "expands_to"})

    for key, value in dict(intent.get("constraints") or {}).items():
        node_id = f"constraint_{key}"
        nodes.append(_claim_node(node_id, "constraint", str(value), key=key))
        edges.append({"source": "intent", "target": node_id, "relation": "bounded_by"})

    for index, claim in enumerate(list(intent.get("claims", []))):
        node_id = f"claim_{index}"
        nodes.append(_claim_node(node_id, "claim", str(claim.get("value", "")), claim_type=str(claim.get("type", ""))))
        edges.append({"source": "request", "target": node_id, "relation": "states"})

    for index, step in enumerate(list((plan or {}).get("steps", []))):
        node_id = f"step_{index}"
        kind = str(step.get("kind", "")).strip()
        nodes.append(_claim_node(node_id, "step", kind, target=step.get("target")))
        edges.append({"source": "intent", "target": node_id, "relation": "depends_on"})

    for index, result in enumerate(results):
        node_id = f"result_{index}"
        kind = str(result.get("kind", "")).strip()
        nodes.append(_claim_node(node_id, "result", kind, ok=bool(result.get("ok", False)), reason=result.get("reason", "")))
        if index < len(list((plan or {}).get("steps", []))):
            edges.append({"source": f"step_{index}", "target": node_id, "relation": "verified_by"})

    return {"nodes": nodes, "edges": edges}


def _issue(issue_type: str, code: str, message: str, *, blocking: bool = True, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "type": issue_type,
        "code": code,
        "message": message,
        "blocking": bool(blocking),
        "details": dict(details or {}),
    }


def _detect_self_conflicts(cwd: str) -> list[dict[str, Any]]:
    signals = _continuity_signals(cwd)
    issues: list[dict[str, Any]] = []
    if signals["has_contradiction"]:
        issues.append(
            _issue(
                "self_model",
                "self_contradiction_active",
                "Active self contradiction blocks stable output.",
                details={"issues": signals["issues"]},
            )
        )
    if not signals["same_system"]:
        issues.append(
            _issue(
                "self_model",
                "identity_continuity_broken",
                "Identity continuity is broken, so the current branch cannot be trusted.",
                details={"continuity_score": signals["continuity_score"]},
            )
        )
    return issues


def _detect_goal_conflicts(request: str, plan: dict[str, Any] | None, results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    intent = str(((plan or {}).get("intent") or {}).get("intent", "observe"))
    step_kinds = _step_kind_set(plan, results)
    if intent not in _STATUS_INTENTS:
        return []
    mutation_kinds = sorted(kind for kind in step_kinds if kind in _MUTATING_STEP_KINDS)
    if not mutation_kinds:
        return []
    return [
        _issue(
            "goal",
            "status_request_mutated_state",
            "A read-only request resolved into mutating actions.",
            details={"intent": intent, "mutation_kinds": mutation_kinds, "request": request.strip()},
        )
    ]


def _detect_context_conflicts(request: str, plan: dict[str, Any] | None, results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    urls = _urls_in_request(request)
    if not urls:
        return []
    serialized_targets = json.dumps(
        {
            "steps": [step.get("target") for step in list((plan or {}).get("steps", []))],
            "results": [item.get("result") for item in results],
        },
        sort_keys=True,
        default=str,
    )
    missing_urls = [url for url in urls if url not in serialized_targets]
    if not missing_urls:
        return []
    return [
        _issue(
            "context",
            "request_context_dropped",
            "Part of the request context disappeared from the planned or executed branch.",
            details={"missing_urls": missing_urls},
        )
    ]


def _detect_evidence_conflicts(run_ok: bool, results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    if run_ok and any(not bool(item.get("ok", False)) for item in results):
        issues.append(
            _issue(
                "evidence",
                "run_status_mismatch",
                "The run is marked successful even though at least one step failed.",
            )
        )
    for item in results:
        reason = str(item.get("reason", "")).strip()
        if reason == "unknown_step":
            issues.append(
                _issue(
                    "evidence",
                    "unknown_step_executed",
                    "The branch contains a step with no execution contract.",
                    details={"kind": item.get("kind", "")},
                )
            )
        if reason == "policy_denied":
            issues.append(
                _issue(
                    "evidence",
                    "policy_contract_violation",
                    "The branch requested an action that violates the current action policy.",
                    details={"kind": item.get("kind", "")},
                )
            )
    return issues


def _detect_consequence_conflicts(plan: dict[str, Any] | None, results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    step_kinds = _step_kind_set(plan, results)
    remediation_kinds = sorted(kind for kind in step_kinds if kind in _HIGH_RISK_REMEDIATION_KINDS)
    if len(remediation_kinds) < 2:
        return []
    return [
        _issue(
            "consequence",
            "conflicting_recovery_branches",
            "Multiple high-risk remediation branches were selected in the same run.",
            details={"remediation_kinds": remediation_kinds},
        )
    ]


def _workflow_signals(cwd: str) -> dict[str, Any]:
    from zero_os.phase_runtime import zero_ai_runtime_status
    from zero_os.zero_ai_control_workflows import zero_ai_control_workflows_status

    return {
        "runtime": zero_ai_runtime_status(cwd),
        "workflows": zero_ai_control_workflows_status(cwd),
    }


def _evolution_signals(cwd: str) -> dict[str, Any]:
    from zero_os.zero_ai_evolution import zero_ai_evolution_status
    from zero_os.zero_ai_source_evolution import zero_ai_source_evolution_status

    return {
        "bounded": zero_ai_evolution_status(cwd),
        "source": zero_ai_source_evolution_status(cwd),
    }


def _detect_workflow_conflicts(cwd: str, plan: dict[str, Any] | None, results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    step_kinds = _step_kind_set(plan, results)
    if not step_kinds:
        return []
    signals = _workflow_signals(cwd)
    runtime = dict(signals.get("runtime") or {})
    lanes = dict((signals.get("workflows") or {}).get("lanes") or {})
    issues: list[dict[str, Any]] = []

    lane_checks = {
        "browser": {"step_kinds": {"browser_action", "browser_open", "browser_dom_inspect", "browser_status"}, "label": "browser"},
        "store_install": {"step_kinds": {"store_install", "store_status"}, "label": "store_install"},
        "recovery": {"step_kinds": {"recover"}, "label": "recovery"},
        "self_repair": {"step_kinds": {"self_repair"}, "label": "self_repair"},
    }
    for lane_key, spec in lane_checks.items():
        if not step_kinds & set(spec["step_kinds"]):
            continue
        lane = dict(lanes.get(lane_key) or {})
        if lane and bool(lane.get("ready", False)) and bool(lane.get("active", False)):
            continue
        issues.append(
            _issue(
                "workflow",
                "typed_workflow_not_ready",
                "A selected branch depends on a typed workflow lane that is not ready.",
                details={"lane": spec["label"], "workflow": lane},
            )
        )

    runtime_missing = bool(runtime.get("missing", False))
    if {"recover", "self_repair", "store_install"} & step_kinds and not runtime_missing and not bool(runtime.get("runtime_ready", False)):
        issues.append(
            _issue(
                "workflow",
                "runtime_not_ready_for_mutation",
                "High-impact workflow steps were selected while the runtime control plane is not ready.",
                details={"runtime_ready": bool(runtime.get("runtime_ready", False)), "runtime_missing": runtime_missing},
            )
        )
    return issues


def _detect_evolution_conflicts(cwd: str, plan: dict[str, Any] | None, results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    step_kinds = _step_kind_set(plan, results)
    if not step_kinds & {"evolution_auto_run", "source_evolution_auto_run"}:
        return []
    signals = _evolution_signals(cwd)
    bounded = dict(signals.get("bounded") or {})
    source = dict(signals.get("source") or {})
    issues: list[dict[str, Any]] = []
    if "evolution_auto_run" in step_kinds and not bool(bounded.get("self_evolution_ready", False)):
        issues.append(
            _issue(
                "evolution",
                "bounded_evolution_not_ready",
                "The branch selected bounded self-evolution while its safety preconditions are not satisfied.",
                details={"blocked_reasons": list(bounded.get("blocked_reasons", []))},
            )
        )
    if "source_evolution_auto_run" in step_kinds and not bool(source.get("source_evolution_ready", False)):
        issues.append(
            _issue(
                "evolution",
                "source_evolution_not_ready",
                "The branch selected guarded source evolution while its safety preconditions are not satisfied.",
                details={"blocked_reasons": list((source.get("proposal") or {}).get("blocked_reasons", []))},
            )
        )
    return issues


def _detect_plan_contract_conflicts(plan: dict[str, Any] | None) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for step in list((plan or {}).get("steps", [])):
        kind = str(step.get("kind", "")).strip()
        if not kind:
            issues.append(
                _issue(
                    "evidence",
                    "missing_step_kind",
                    "A candidate branch contains a step with no kind.",
                    details={"step": step},
                )
            )
            continue
        if kind not in _KNOWN_STEP_KINDS:
            issues.append(
                _issue(
                    "evidence",
                    "unknown_step_kind",
                    "A candidate branch contains a step with no typed execution contract.",
                    details={"kind": kind},
                )
            )
    return issues


def _stable_claims(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    claims: list[dict[str, Any]] = []
    for item in results:
        kind = str(item.get("kind", "step")).strip() or "step"
        if item.get("ok", False):
            claims.append({"kind": kind, "claim": f"{kind} executed under its current contract."})
            continue
        reason = str(item.get("reason", "")).strip()
        if reason == "approval_required":
            claims.append({"kind": kind, "claim": f"{kind} is blocked on approval, so no unsupported action was taken."})
        elif reason:
            claims.append({"kind": kind, "claim": f"{kind} stopped with reason={reason}."})
        else:
            claims.append({"kind": kind, "claim": f"{kind} did not complete successfully."})
    if not claims:
        claims.append({"kind": "observe", "claim": "No action was taken."})
    return claims


def _stable_branch_claims(plan: dict[str, Any] | None) -> list[dict[str, Any]]:
    claims: list[dict[str, Any]] = []
    intent = dict((plan or {}).get("intent") or {})
    branch = dict((plan or {}).get("branch") or {})
    steps = list((plan or {}).get("steps", []))
    if branch:
        claims.append(
            {
                "kind": "branch",
                "claim": f"Candidate branch {branch.get('id', 'primary')} survives contradiction pressure before execution.",
            }
        )
    if steps:
        claims.append({"kind": "steps", "claim": f"Candidate branch keeps {len(steps)} typed step(s) attached to the goal."})
    else:
        claims.append({"kind": "observe", "claim": "Candidate branch compresses to observation only."})
    if intent:
        claims.append({"kind": "intent", "claim": f"Candidate branch matches intent={intent.get('intent', 'observe')}."})
    return claims


def _coverage_targets(request: str, plan: dict[str, Any] | None) -> tuple[int, int]:
    intent = dict((plan or {}).get("intent") or {})
    serialized_targets = json.dumps(
        [step.get("target") for step in list((plan or {}).get("steps", []))],
        sort_keys=True,
        default=str,
    )
    covered = 0
    total = 0

    for url in _urls_in_request(request):
        total += 1
        if url in serialized_targets:
            covered += 1

    expected_steps = set(_INTENT_STEP_EXPECTATIONS.get(str(intent.get("intent", "observe")), set()))
    if expected_steps:
        total += 1
        step_kinds = {str(step.get("kind", "")).strip() for step in list((plan or {}).get("steps", []))}
        if step_kinds & expected_steps:
            covered += 1

    if total == 0:
        total = 1
        covered = 1 if list((plan or {}).get("steps", [])) else 0
    return covered, total


def _branch_scores(request: str, plan: dict[str, Any] | None, issues: list[dict[str, Any]]) -> dict[str, int]:
    contradiction_count = sum(1 for item in issues if item.get("blocking", True))
    issue_types = {str(item.get("type", "")) for item in issues}
    covered, total = _coverage_targets(request, plan)
    step_count = len(list((plan or {}).get("steps", [])))
    evidence = dict((plan or {}).get("evidence") or {})
    evidence_weight = float(evidence.get("total_weight", 0.0) or 0.0)
    memory_weight = float(evidence.get("memory_weight", 0.0) or 0.0)
    core_law_weight = float(evidence.get("core_law_weight", 0.0) or 0.0)
    truth_base = 100 if "self_model" not in issue_types and "evidence" not in issue_types else 0
    truth = int(round((truth_base * 0.7) + (evidence_weight * 100.0 * 0.3)))
    consistency = max(0, 100 - (contradiction_count * 30))
    consistency = int(round((consistency * 0.8) + (memory_weight * 100.0 * 0.2)))
    goal_fit = int(round((((covered / max(total, 1)) * 100.0) * 0.75) + (evidence_weight * 100.0 * 0.25)))
    consequence = 100 if "consequence" not in issue_types else 0
    consequence = int(round((consequence * 0.85) + (core_law_weight * 100.0 * 0.15)))
    return {
        "truth": truth,
        "consistency": consistency,
        "goal_fit": goal_fit,
        "consequence": consequence,
        "efficiency": max(0, 100 - max(step_count - 1, 0) * 8),
        "style": 100,
    }


def _branch_sort_key(review: dict[str, Any]) -> tuple[Any, ...]:
    scores = dict(review.get("scores") or {})
    branch = dict(review.get("branch") or {})
    evidence = dict(review.get("evidence") or {})
    return tuple(
        list(scores.get(name, 0) for name in _PRIORITY_ORDER)
        + [
            int(round(float(evidence.get("total_weight", 0.0) or 0.0) * 1000)),
            int(round(float(evidence.get("memory_weight", 0.0) or 0.0) * 1000)),
            1 if branch.get("preferred", False) else 0,
            -int(branch.get("step_count", 0) or 0),
        ]
    )


def _recommended_action(issues: list[dict[str, Any]]) -> str:
    codes = {item["code"] for item in issues}
    if "self_contradiction_active" in codes or "identity_continuity_broken" in codes:
        return "Resolve self contradictions before any broader self-upgrade."
    if "status_request_mutated_state" in codes:
        return "Split read-only observation from mutating workflows so the branch matches the user goal."
    if "request_context_dropped" in codes:
        return "Rebuild the branch so every explicit request target remains attached to at least one step."
    if "conflicting_recovery_branches" in codes:
        return "Choose one guarded remediation branch and rerun instead of mixing recovery and self-repair."
    if "typed_workflow_not_ready" in codes:
        return "Refresh the typed workflow lane or choose a ready subsystem before executing that branch."
    if "runtime_not_ready_for_mutation" in codes:
        return "Restore runtime readiness before allowing high-impact workflow branches."
    if "bounded_evolution_not_ready" in codes or "source_evolution_not_ready" in codes:
        return "Stabilize runtime, continuity, and agent health before allowing evolution branches."
    if "unknown_step_kind" in codes or "missing_step_kind" in codes:
        return "Regenerate the branch from typed steps only before execution."
    if "policy_contract_violation" in codes:
        return "Route the action through a typed safe workflow instead of a denied raw action."
    if "unknown_step_executed" in codes:
        return "Add a typed execution contract before allowing that step back into planning."
    return "Maintain the contradiction gate and extend typed reasoning checks across more subsystems."


def review_run(
    cwd: str,
    request: str,
    plan: dict[str, Any] | None,
    results: list[dict[str, Any]] | None,
    *,
    run_ok: bool | None = None,
    persist: bool = True,
    mode: str = "run",
) -> dict[str, Any]:
    result_list = list(results or [])
    graph = build_claim_graph(request, plan, result_list)
    computed_ok = all(bool(item.get("ok", False)) for item in result_list) if result_list else True
    effective_ok = computed_ok if run_ok is None else bool(run_ok)
    issues = (
        _detect_self_conflicts(cwd)
        + _detect_goal_conflicts(request, plan, result_list)
        + _detect_context_conflicts(request, plan, result_list)
        + _detect_workflow_conflicts(cwd, plan, result_list)
        + _detect_evolution_conflicts(cwd, plan, result_list)
        + _detect_plan_contract_conflicts(plan)
        + _detect_evidence_conflicts(effective_ok, result_list)
        + _detect_consequence_conflicts(plan, result_list)
    )
    contradiction_count = sum(1 for item in issues if item.get("blocking", True))
    decision = "allow" if contradiction_count == 0 else "hold"
    stable_claim_set = _stable_branch_claims(plan) if mode == "branch" else _stable_claims(result_list)
    recommended_action = _recommended_action(issues)
    scores = _branch_scores(request, plan, issues)
    boundary_summary = ""
    if decision != "allow":
        reason = issues[0]["message"] if issues else "Unresolved contradiction detected."
        boundary_summary = "\n".join(
            [
                "contradiction gate: hold",
                f"reason: {reason}",
                f"next: {recommended_action}",
            ]
        )

    review = {
        "ok": True,
        "enabled": True,
        "decision": decision,
        "contradiction_count": contradiction_count,
        "priority_order": list(_PRIORITY_ORDER),
        "checks": list(_CHECKS),
        "issues": issues,
        "stable_claims": stable_claim_set,
        "claim_graph": graph,
        "scores": scores,
        "evidence": dict((plan or {}).get("evidence") or {}),
        "memory_context": dict((plan or {}).get("memory_context") or {}),
        "recommended_action": recommended_action,
        "boundary_summary": boundary_summary,
        "continuity": _continuity_signals(cwd),
        "last_checked_utc": _utc_now(),
        "mode": mode,
        "branch": {
            "id": str(((plan or {}).get("branch") or {}).get("id", "primary")),
            "source": str(((plan or {}).get("branch") or {}).get("source", "direct_plan")),
            "note": str(((plan or {}).get("branch") or {}).get("note", "")),
            "preferred": bool(((plan or {}).get("branch") or {}).get("preferred", False)),
            "step_count": len(list((plan or {}).get("steps", []))),
        },
    }

    if cwd and persist:
        path = _path(cwd)
        state = _load(path, _default_state())
        state["enabled"] = True
        state["last_decision"] = decision
        state["last_checked_utc"] = review["last_checked_utc"]
        state["last_contradiction_count"] = contradiction_count
        state["last_request"] = request.strip()
        state["last_plan_intent"] = str(((plan or {}).get("intent") or {}).get("intent", "observe"))
        state["last_issues"] = issues[:8]
        state["last_mode"] = mode
        history = list(state.get("history", []))
        history.append(
            {
                "checked_utc": review["last_checked_utc"],
                "decision": decision,
                "contradiction_count": contradiction_count,
                "request": request.strip(),
                "mode": mode,
            }
        )
        state["history"] = history[-20:]
        _save(path, state)
        review["path"] = str(path)
    return review


def review_branch(cwd: str, request: str, plan: dict[str, Any] | None, *, persist: bool = False) -> dict[str, Any]:
    return review_run(cwd, request, plan, [], run_ok=True, persist=persist, mode="branch")


def select_stable_branch(cwd: str, request: str, candidates: list[dict[str, Any]]) -> dict[str, Any]:
    reviews: list[dict[str, Any]] = []
    for candidate in candidates:
        plan = dict(candidate)
        review = review_branch(cwd, request, plan, persist=False)
        review["plan"] = plan
        reviews.append(review)

    allowed = [review for review in reviews if review.get("decision") == "allow"]
    allowed.sort(key=_branch_sort_key, reverse=True)
    selected = allowed[0] if allowed else None
    discarded = [review for review in reviews if review is not selected]
    blocked = None
    if not selected and reviews:
        ranked = sorted(reviews, key=_branch_sort_key, reverse=True)
        blocked = ranked[0]
        review_branch(cwd, request, dict(blocked.get("plan") or {}), persist=True)

    return {
        "ok": True,
        "candidate_count": len(reviews),
        "selected_branch": selected,
        "selected_plan": dict(selected.get("plan") or {}) if selected else None,
        "discarded_branches": discarded,
        "discarded_count": len(discarded),
        "blocked_branch": blocked,
        "reviews": reviews,
    }


def contradiction_engine_status(cwd: str) -> dict[str, Any]:
    path = _path(cwd)
    state = _load(path, _default_state())
    continuity = _continuity_signals(cwd)
    highest_value_steps: list[str] = []
    if continuity["has_contradiction"] or not continuity["same_system"]:
        highest_value_steps.append("Resolve self contradictions before trusting broader autonomous reasoning.")
    elif not bool(state.get("enabled", True)):
        highest_value_steps.append("Enable the contradiction gate so every response is checked before output.")
    elif str(state.get("last_decision", "unknown")) == "hold":
        highest_value_steps.append(_recommended_action(list(state.get("last_issues", []))))
    else:
        highest_value_steps.append("Maintain the contradiction gate and extend typed reasoning checks across more subsystems.")

    return {
        "ok": True,
        "path": str(path),
        "enabled": bool(state.get("enabled", True)),
        "active": bool(state.get("enabled", True)),
        "ready": True,
        "priority_order": list(state.get("priority_order", list(_PRIORITY_ORDER))),
        "checks": list(state.get("checks", list(_CHECKS))),
        "last_decision": str(state.get("last_decision", "unknown")),
        "last_checked_utc": str(state.get("last_checked_utc", "")),
        "last_contradiction_count": int(state.get("last_contradiction_count", 0) or 0),
        "last_request": str(state.get("last_request", "")),
        "last_plan_intent": str(state.get("last_plan_intent", "")),
        "last_mode": str(state.get("last_mode", "")),
        "last_issues": list(state.get("last_issues", [])),
        "history_count": len(list(state.get("history", []))),
        "continuity": continuity,
        "highest_value_steps": highest_value_steps,
    }


def contradiction_engine_refresh(cwd: str) -> dict[str, Any]:
    return contradiction_engine_status(cwd)
