from __future__ import annotations

from zero_os.agent_permission_policy import audit_event, classify_action
from zero_os.api_connector_profiles import profile_request, profile_workflow
from zero_os.approval_workflow import latest_approved, latest_pending, mark_executed, request_approval
from zero_os.browser_dom_automation import act as browser_dom_act, inspect_page as browser_dom_inspect, status as browser_dom_status
from zero_os.browser_session_connector import browser_session_action, browser_session_open, browser_session_status
from zero_os.autonomous_fix_gate import autonomy_evaluate
from zero_os.cloud_deploy_integration import configure_target as cloud_target_set, deploy as cloud_deploy, status as cloud_status
from zero_os.connector_layer import run_recovery, run_self_repair, store_install, store_status, web_fetch
from zero_os.contradiction_engine import contradiction_engine_status
from zero_os.flow_monitor import flow_scan
from zero_os.github_integration_pack import (
    connect_repo as github_connect,
    issue_act as github_issue_act,
    issue_comments as github_issue_comments,
    issue_plan as github_issue_plan,
    issue_reply_draft as github_issue_reply_draft,
    issue_reply_post as github_issue_reply_post,
    issue_read as github_issue_read,
    issue_summary as github_issues,
    pr_comments as github_pr_comments,
    pr_act as github_pr_act,
    pr_plan as github_pr_plan,
    pr_reply_draft as github_pr_reply_draft,
    pr_reply_post as github_pr_reply_post,
    pr_read as github_pr_read,
    pr_summary as github_prs,
    status as github_status,
)
from zero_os.internet_capability import internet_capability_status
from zero_os.observation_layer import collect_observations
from zero_os.smart_workspace import workspace_status
from zero_os.subsystem_controller_registry import controller_registry_status
from zero_os.tool_capability_registry import registry_status
from zero_os.verification_web_flow import verify_web_lookup


def _dispatch_via_highway(cwd: str, text: str) -> dict:
    from zero_os.highway import Highway

    result = Highway(cwd=cwd)._dispatch_non_agent(text, cwd)
    return {"capability": result.capability, "summary": result.summary}


def _approval_payload(run_id: str, target, **extra) -> dict:
    payload = {"run_id": str(run_id or "").strip(), "target": target}
    payload.update(extra)
    return payload


def _matching_approval(cwd: str, action: str, run_id: str, target):
    approved = latest_approved(cwd, action, run_id=str(run_id or "").strip(), target=target)
    if approved.get("ok", False):
        return {"approved": approved, "pending": {"ok": False, "reason": "none"}}
    pending = latest_pending(cwd, action, run_id=str(run_id or "").strip(), target=target)
    return {"approved": approved, "pending": pending}


def _browser_action_target(cwd: str, target: dict) -> dict:
    payload = dict(target or {})
    if str(payload.get("url", "")).strip():
        return payload
    session = browser_session_status(cwd)
    payload["url"] = str(session.get("last_opened", "")).strip()
    return payload


def _planner_gate_kwargs(plan_context: dict | None) -> dict:
    context = dict(plan_context or {})
    return {
        "planner_confidence": context.get("planner_confidence"),
        "planner_risk_level": context.get("risk_level"),
        "planner_ambiguity_count": len(list(context.get("ambiguity_flags", []))),
        "planner_execution_mode": context.get("execution_mode"),
        "planner_strategy": context.get("smart_strategy"),
    }


def execute_step(cwd: str, step: dict, *, run_id: str = "", plan_context: dict | None = None) -> dict:
    kind = step.get("kind", "")
    target = step.get("target", "")
    execution_mode = str(dict(plan_context or {}).get("execution_mode", "normal") or "normal")
    policy = classify_action(cwd, kind)
    if policy["decision"] == "deny":
        audit_event(cwd, kind, "denied", {"target": target})
        return {"ok": False, "kind": kind, "reason": "policy_denied"}
    if policy["decision"] == "observe_only" and kind not in {"observe", "system_status", "tool_registry", "browser_status", "browser_dom_inspect", "web_verify", "web_fetch", "store_status", "autonomy_gate"}:
        audit_event(cwd, kind, "observe_only_blocked", {"target": target})
        return {"ok": False, "kind": kind, "reason": "policy_observe_only", "policy": policy}
    if kind == "observe":
        audit_event(cwd, kind, "executed", {"target": target})
        return {"ok": True, "kind": kind, "result": collect_observations(cwd)}
    if kind == "system_status":
        audit_event(cwd, kind, "executed", {"target": target})
        return {"ok": True, "kind": kind, "result": collect_observations(cwd)}
    if kind == "tool_registry":
        audit_event(cwd, kind, "executed", {"target": target})
        return {"ok": True, "kind": kind, "result": registry_status(cwd)}
    if kind == "controller_registry":
        audit_event(cwd, kind, "executed", {"target": target})
        return {"ok": True, "kind": kind, "result": controller_registry_status(cwd)}
    if kind == "capability_expansion_protocol":
        audit_event(cwd, kind, "executed", {"target": target})
        return {"ok": True, "kind": kind, "result": {"ok": True, "protocol": "capability_expansion_protocol", "active": True}}
    if kind == "general_agent":
        audit_event(cwd, kind, "executed", {"target": target})
        return {"ok": True, "kind": kind, "result": {"ok": True, "general_agent": True, "status": "bounded_ready"}}
    if kind == "domain_pack_generate_feature":
        audit_event(cwd, kind, "executed", {"target": target})
        return {"ok": True, "kind": kind, "result": {"ok": True, "feature_request": str(target), "generator": "domain_pack_factory"}}
    if kind == "contradiction_engine":
        audit_event(cwd, kind, "executed", {"target": target})
        return {"ok": True, "kind": kind, "result": contradiction_engine_status(cwd)}
    if kind == "pressure_harness":
        from zero_os.zero_ai_pressure_harness import pressure_harness_run

        audit_event(cwd, kind, "executed", {"target": target})
        return {"ok": True, "kind": kind, "result": pressure_harness_run(cwd)}
    if kind == "smart_workspace":
        audit_event(cwd, kind, "executed", {"target": target})
        return {"ok": True, "kind": kind, "result": workspace_status(cwd, str(target or "main"))}
    if kind == "maintenance_orchestrator":
        from zero_os.maintenance_orchestrator import maintenance_status

        audit_event(cwd, kind, "executed", {"target": target})
        return {"ok": True, "kind": kind, "result": maintenance_status(cwd)}
    if kind == "internet_capability":
        audit_event(cwd, kind, "executed", {"target": target})
        return {"ok": True, "kind": kind, "result": internet_capability_status(cwd)}
    if kind == "world_class_readiness":
        from zero_os.world_class_readiness import world_class_readiness_status

        audit_event(cwd, kind, "executed", {"target": target})
        return {"ok": True, "kind": kind, "result": world_class_readiness_status(cwd)}
    if kind == "flow_monitor":
        audit_event(cwd, kind, "executed", {"target": target})
        return {"ok": True, "kind": kind, "result": flow_scan(cwd, str(target or "."))}
    if kind == "browser_status":
        audit_event(cwd, kind, "executed", {"target": target})
        return {"ok": True, "kind": kind, "result": browser_session_status(cwd)}
    if kind == "browser_dom_inspect":
        audit_event(cwd, kind, "executed", {"target": target})
        return {"ok": True, "kind": kind, "result": browser_dom_inspect(cwd, str(target))}
    if kind == "web_verify":
        audit_event(cwd, kind, "executed", {"target": target})
        return {"ok": True, "kind": kind, "result": verify_web_lookup(str(target))}
    if kind == "web_fetch":
        audit_event(cwd, kind, "executed", {"target": target})
        return {"ok": True, "kind": kind, "result": web_fetch(str(target))}
    if kind == "browser_open":
        audit_event(cwd, kind, "executed", {"target": target})
        return {"ok": True, "kind": kind, "result": browser_session_open(cwd, str(target))}
    if kind == "browser_action":
        effective_target = _browser_action_target(cwd, dict(target or {}))
        if execution_mode == "safe":
            action_name = str(effective_target.get("action", "")).strip().lower()
            selector = str(effective_target.get("selector", "")).strip().lower()
            if action_name in {"click", "submit"} and selector in {"", "body"}:
                audit_event(cwd, kind, "safe_mode_blocked", {"target": effective_target, "execution_mode": execution_mode})
                return {"ok": False, "kind": kind, "reason": "safe_mode_requires_specific_selector", "execution_mode": execution_mode}
        approval_state = _matching_approval(cwd, "browser_action", run_id, effective_target)
        approved = approval_state["approved"]
        if approved.get("ok", False):
            approval_payload = approved["approval"].get("payload", {})
            effective_target = _browser_action_target(cwd, dict(approval_payload.get("target", effective_target) or effective_target))
            audit_event(cwd, kind, "executed_after_approval", {"target": effective_target})
            result = browser_dom_act(cwd, str(effective_target.get("url", "")), str(effective_target.get("action", "")), str(effective_target.get("selector", "")), str(effective_target.get("value", "")))
            mark_executed(cwd, str(approved["approval"].get("id", "")), outcome="ok" if result.get("ok", False) else "failed")
            return {
                "ok": True,
                "kind": kind,
                "result": result,
            }
        gate = autonomy_evaluate(
            cwd,
            action=f"browser action {effective_target.get('action', '')}",
            blast_radius="service",
            reversible=True,
            evidence_count=8,
            contradictory_signals=0,
            independent_verifiers=2,
            checks={"browser_session": True, "verification_ready": True, "rollback_ready": True},
            **_planner_gate_kwargs(plan_context),
        )
        if policy["decision"] == "approval_required":
            pending = approval_state["pending"]
            if pending.get("ok", False):
                audit_event(cwd, kind, "approval_required", {"target": effective_target, "reused_pending": True})
                return {"ok": False, "kind": kind, "reason": "approval_required", "approval": pending}
            audit_event(cwd, kind, "approval_required", {"target": effective_target})
            approval = request_approval(cwd, "browser_action", "interactive_browser_action_requires_approval", _approval_payload(run_id, effective_target, gate=gate))
            return {"ok": False, "kind": kind, "reason": "approval_required", "gate": gate, "approval": approval}
        if gate.get("decision") != "allow":
            return {"ok": False, "kind": kind, "reason": "autonomy_gate", "gate": gate}
        audit_event(cwd, kind, "executed_guarded_auto", {"target": effective_target})
        return {
            "ok": True,
            "kind": kind,
            "result": browser_dom_act(cwd, str(effective_target.get("url", "")), str(effective_target.get("action", "")), str(effective_target.get("selector", "")), str(effective_target.get("value", ""))),
            "gate": gate,
            "policy": policy,
        }
    if kind == "api_request":
        audit_event(cwd, kind, "executed", {"target": target})
        return {"ok": True, "kind": kind, "result": profile_request(cwd, str(target.get("profile", "")), str(target.get("path", "")))}
    if kind == "api_workflow":
        audit_event(cwd, kind, "executed", {"target": target})
        return {"ok": True, "kind": kind, "result": profile_workflow(cwd, str(target.get("profile", "")), list(target.get("paths", [])))}
    if kind == "github_connect":
        audit_event(cwd, kind, "executed", {"target": target})
        return {"ok": True, "kind": kind, "result": github_connect(cwd, str(target))}
    if kind == "github_issues":
        audit_event(cwd, kind, "executed", {"target": target})
        return {"ok": True, "kind": kind, "result": github_issues(cwd, str(target))}
    if kind == "github_prs":
        audit_event(cwd, kind, "executed", {"target": target})
        return {"ok": True, "kind": kind, "result": github_prs(cwd, str(target))}
    if kind == "github_pr_comments":
        audit_event(cwd, kind, "executed", {"target": target})
        return {"ok": True, "kind": kind, "result": github_pr_comments(cwd, str(target.get("repo", "")), int(target.get("pr", 0)))}
    if kind == "github_issue_read":
        audit_event(cwd, kind, "executed", {"target": target})
        return {"ok": True, "kind": kind, "result": github_issue_read(cwd, str(target.get("repo", "")), int(target.get("issue", 0)))}
    if kind == "github_issue_comments":
        audit_event(cwd, kind, "executed", {"target": target})
        return {"ok": True, "kind": kind, "result": github_issue_comments(cwd, str(target.get("repo", "")), int(target.get("issue", 0)))}
    if kind == "github_issue_plan":
        audit_event(cwd, kind, "executed", {"target": target})
        return {"ok": True, "kind": kind, "result": github_issue_plan(cwd, str(target.get("repo", "")), int(target.get("issue", 0)))}
    if kind == "github_issue_act":
        audit_event(cwd, kind, "executed", {"target": target})
        return {
            "ok": True,
            "kind": kind,
            "result": github_issue_act(
                cwd,
                str(target.get("repo", "")),
                int(target.get("issue", 0)),
                bool(target.get("execute", False)),
            ),
        }
    if kind == "github_issue_reply_draft":
        audit_event(cwd, kind, "executed", {"target": target})
        return {
            "ok": True,
            "kind": kind,
            "result": github_issue_reply_draft(
                cwd,
                str(target.get("repo", "")),
                int(target.get("issue", 0)),
                bool(target.get("execute", False)),
            ),
        }
    if kind == "github_issue_reply_post":
        audit_event(cwd, kind, "executed", {"target": target})
        return {
            "ok": True,
            "kind": kind,
            "result": github_issue_reply_post(
                cwd,
                str(target.get("repo", "")),
                int(target.get("issue", 0)),
                str(target.get("text", "")),
            ),
        }
    if kind == "github_pr_read":
        audit_event(cwd, kind, "executed", {"target": target})
        return {"ok": True, "kind": kind, "result": github_pr_read(cwd, str(target.get("repo", "")), int(target.get("pr", 0)))}
    if kind == "github_pr_plan":
        audit_event(cwd, kind, "executed", {"target": target})
        return {"ok": True, "kind": kind, "result": github_pr_plan(cwd, str(target.get("repo", "")), int(target.get("pr", 0)))}
    if kind == "github_pr_act":
        audit_event(cwd, kind, "executed", {"target": target})
        return {
            "ok": True,
            "kind": kind,
            "result": github_pr_act(
                cwd,
                str(target.get("repo", "")),
                int(target.get("pr", 0)),
                bool(target.get("execute", False)),
            ),
        }
    if kind == "github_pr_reply_draft":
        audit_event(cwd, kind, "executed", {"target": target})
        return {
            "ok": True,
            "kind": kind,
            "result": github_pr_reply_draft(
                cwd,
                str(target.get("repo", "")),
                int(target.get("pr", 0)),
                bool(target.get("execute", False)),
            ),
        }
    if kind == "github_pr_reply_post":
        audit_event(cwd, kind, "executed", {"target": target})
        return {
            "ok": True,
            "kind": kind,
            "result": github_pr_reply_post(
                cwd,
                str(target.get("repo", "")),
                int(target.get("pr", 0)),
                str(target.get("text", "")),
            ),
        }
    if kind == "cloud_target_set":
        audit_event(cwd, kind, "executed", {"target": target})
        return {"ok": True, "kind": kind, "result": cloud_target_set(cwd, str(target.get("name", "")), str(target.get("provider", "")))}
    if kind == "cloud_deploy":
        audit_event(cwd, kind, "executed", {"target": target})
        return {"ok": True, "kind": kind, "result": cloud_deploy(cwd, str(target.get("target", "")), str(target.get("artifact", "")))}
    if kind == "highway_dispatch":
        audit_event(cwd, kind, "executed", {"target": target})
        return {"ok": True, "kind": kind, "result": _dispatch_via_highway(cwd, str(target))}
    if kind == "store_status":
        audit_event(cwd, kind, "executed", {"target": target})
        return {"ok": True, "kind": kind, "result": store_status(cwd)}
    if kind == "store_install":
        if policy["decision"] == "approval_required":
            approval_state = _matching_approval(cwd, "store_install", run_id, target)
            approved = approval_state["approved"]
            if not approved.get("ok", False):
                pending = approval_state["pending"]
                if pending.get("ok", False):
                    audit_event(cwd, kind, "approval_required", {"target": target, "reused_pending": True})
                    return {"ok": False, "kind": kind, "reason": "approval_required", "approval": pending}
                audit_event(cwd, kind, "approval_required", {"target": target})
                approval = request_approval(cwd, "store_install", "policy_requires_approval", _approval_payload(run_id, target))
                return {"ok": False, "kind": kind, "reason": "approval_required", "approval": approval}
        gate = autonomy_evaluate(
            cwd,
            action=f"native store install {target}",
            blast_radius="service",
            reversible=True,
            evidence_count=9,
            contradictory_signals=0,
            independent_verifiers=3,
            checks={"store_ready": True, "rollback_ready": True, "verification_ready": True},
            **_planner_gate_kwargs(plan_context),
        )
        if gate.get("decision") != "allow":
            return {"ok": False, "kind": kind, "reason": "autonomy_gate", "gate": gate}
        result = store_install(cwd, str(target), "")
        approved = _matching_approval(cwd, "store_install", run_id, target)["approved"]
        if approved.get("ok", False):
            mark_executed(cwd, str(approved["approval"].get("id", "")), outcome="ok" if result.get("ok", False) else "failed")
        return {"ok": True, "kind": kind, "result": result}
    if kind == "self_repair":
        if policy["decision"] == "approval_required":
            approval_state = _matching_approval(cwd, "self_repair", run_id, target)
            approved = approval_state["approved"]
            if not approved.get("ok", False):
                pending = approval_state["pending"]
                if pending.get("ok", False):
                    audit_event(cwd, kind, "approval_required", {"target": target, "reused_pending": True})
                    return {"ok": False, "kind": kind, "reason": "approval_required", "approval": pending}
                audit_event(cwd, kind, "approval_required", {"target": target})
                approval = request_approval(cwd, "self_repair", "policy_requires_approval", _approval_payload(run_id, target))
                return {"ok": False, "kind": kind, "reason": "approval_required", "approval": approval}
        gate = autonomy_evaluate(
            cwd,
            action="self repair run",
            blast_radius="system",
            reversible=True,
            evidence_count=10,
            contradictory_signals=0,
            independent_verifiers=3,
            checks={"runtime_ready": True, "rollback_ready": False, "verification_ready": True},
            **_planner_gate_kwargs(plan_context),
        )
        if gate.get("decision") != "allow":
            return {"ok": False, "kind": kind, "reason": "autonomy_gate", "gate": gate}
        result = run_self_repair(cwd)
        approved = _matching_approval(cwd, "self_repair", run_id, target)["approved"]
        if approved.get("ok", False):
            mark_executed(cwd, str(approved["approval"].get("id", "")), outcome="ok" if result.get("ok", False) else "failed")
        return {"ok": True, "kind": kind, "result": result}
    if kind == "recover":
        if policy["decision"] == "approval_required":
            approval_state = _matching_approval(cwd, "recover", run_id, target)
            approved = approval_state["approved"]
            if not approved.get("ok", False):
                pending = approval_state["pending"]
                if pending.get("ok", False):
                    audit_event(cwd, kind, "approval_required", {"target": target, "reused_pending": True})
                    return {"ok": False, "kind": kind, "reason": "approval_required", "approval": pending}
                audit_event(cwd, kind, "approval_required", {"target": target})
                approval = request_approval(cwd, "recover", "policy_requires_approval", _approval_payload(run_id, target))
                return {"ok": False, "kind": kind, "reason": "approval_required", "approval": approval}
        gate = autonomy_evaluate(
            cwd,
            action="zero ai recover",
            blast_radius="system",
            reversible=True,
            evidence_count=12,
            contradictory_signals=0,
            independent_verifiers=4,
            checks={"snapshot_ready": True, "rollback_ready": True, "verification_ready": True},
            **_planner_gate_kwargs(plan_context),
        )
        if gate.get("decision") != "allow":
            return {"ok": False, "kind": kind, "reason": "autonomy_gate", "gate": gate}
        result = run_recovery(cwd)
        approved = _matching_approval(cwd, "recover", run_id, target)["approved"]
        if approved.get("ok", False):
            mark_executed(cwd, str(approved["approval"].get("id", "")), outcome="ok" if result.get("ok", False) else "failed")
        return {"ok": True, "kind": kind, "result": result}
    if kind == "autonomy_gate":
        audit_event(cwd, kind, "executed", {"target": target})
        return {
            "ok": True,
            "kind": kind,
            "result": autonomy_evaluate(
                cwd,
                action=str(target),
                blast_radius="system",
                reversible=True,
                evidence_count=10,
                contradictory_signals=0,
                independent_verifiers=3,
                checks={"observation_ready": True, "verification_ready": True, "rollback_ready": True},
                **_planner_gate_kwargs(plan_context),
            ),
        }
    return {"ok": False, "kind": kind, "reason": "unknown_step"}
