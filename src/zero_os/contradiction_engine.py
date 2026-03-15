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
_STATUS_INTENTS = {"planning", "status", "tools"}
_HIGH_RISK_REMEDIATION_KINDS = {"recover", "self_repair"}
_PRIORITY_ORDER = ("truth", "consistency", "goal_fit", "consequence", "efficiency", "style")
_CHECKS = ("self_model", "goal", "context", "evidence", "consequence")


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
) -> dict[str, Any]:
    result_list = list(results or [])
    graph = build_claim_graph(request, plan, result_list)
    computed_ok = all(bool(item.get("ok", False)) for item in result_list) if result_list else True
    effective_ok = computed_ok if run_ok is None else bool(run_ok)
    issues = (
        _detect_self_conflicts(cwd)
        + _detect_goal_conflicts(request, plan, result_list)
        + _detect_context_conflicts(request, plan, result_list)
        + _detect_evidence_conflicts(effective_ok, result_list)
        + _detect_consequence_conflicts(plan, result_list)
    )
    contradiction_count = sum(1 for item in issues if item.get("blocking", True))
    decision = "allow" if contradiction_count == 0 else "hold"
    stable_claim_set = _stable_claims(result_list)
    recommended_action = _recommended_action(issues)
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
        "recommended_action": recommended_action,
        "boundary_summary": boundary_summary,
        "continuity": _continuity_signals(cwd),
        "last_checked_utc": _utc_now(),
    }

    if cwd:
        path = _path(cwd)
        state = _load(path, _default_state())
        state["enabled"] = True
        state["last_decision"] = decision
        state["last_checked_utc"] = review["last_checked_utc"]
        state["last_contradiction_count"] = contradiction_count
        state["last_request"] = request.strip()
        state["last_plan_intent"] = str(((plan or {}).get("intent") or {}).get("intent", "observe"))
        state["last_issues"] = issues[:8]
        history = list(state.get("history", []))
        history.append(
            {
                "checked_utc": review["last_checked_utc"],
                "decision": decision,
                "contradiction_count": contradiction_count,
                "request": request.strip(),
            }
        )
        state["history"] = history[-20:]
        _save(path, state)
        review["path"] = str(path)
    return review


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
        "last_issues": list(state.get("last_issues", [])),
        "history_count": len(list(state.get("history", []))),
        "continuity": continuity,
        "highest_value_steps": highest_value_steps,
    }


def contradiction_engine_refresh(cwd: str) -> dict[str, Any]:
    return contradiction_engine_status(cwd)
