from __future__ import annotations

from zero_os.agent_permission_policy import audit_event, classify_action
from zero_os.api_connector_profiles import profile_request, profile_workflow
from zero_os.approval_workflow import latest_approved, request_approval
from zero_os.browser_dom_automation import act as browser_dom_act, inspect_page as browser_dom_inspect, status as browser_dom_status
from zero_os.browser_session_connector import browser_session_action, browser_session_open, browser_session_status
from zero_os.autonomous_fix_gate import autonomy_evaluate
from zero_os.cloud_deploy_integration import configure_target as cloud_target_set, deploy as cloud_deploy, status as cloud_status
from zero_os.connector_layer import run_recovery, run_self_repair, store_install, store_status, web_fetch
from zero_os.github_integration_pack import connect_repo as github_connect, issue_summary as github_issues, status as github_status
from zero_os.observation_layer import collect_observations
from zero_os.tool_capability_registry import registry_status
from zero_os.verification_web_flow import verify_web_lookup


def _dispatch_via_highway(cwd: str, text: str) -> dict:
    from zero_os.highway import Highway

    result = Highway(cwd=cwd)._dispatch_non_agent(text, cwd)
    return {"capability": result.capability, "summary": result.summary}


def execute_step(cwd: str, step: dict) -> dict:
    kind = step.get("kind", "")
    target = step.get("target", "")
    policy = classify_action(cwd, kind)
    if policy["decision"] == "deny":
        audit_event(cwd, kind, "denied", {"target": target})
        return {"ok": False, "kind": kind, "reason": "policy_denied"}
    if kind == "observe":
        audit_event(cwd, kind, "executed", {"target": target})
        return {"ok": True, "kind": kind, "result": collect_observations(cwd)}
    if kind == "system_status":
        audit_event(cwd, kind, "executed", {"target": target})
        return {"ok": True, "kind": kind, "result": collect_observations(cwd)}
    if kind == "tool_registry":
        audit_event(cwd, kind, "executed", {"target": target})
        return {"ok": True, "kind": kind, "result": registry_status()}
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
        approved = latest_approved(cwd, "browser_action")
        if approved.get("ok", False):
            approval_payload = approved["approval"].get("payload", {})
            effective_target = approval_payload.get("target", target)
            audit_event(cwd, kind, "executed_after_approval", {"target": effective_target})
            return {
                "ok": True,
                "kind": kind,
                "result": browser_dom_act(cwd, str(effective_target.get("url", "")), str(effective_target.get("action", "")), str(effective_target.get("selector", "")), str(effective_target.get("value", ""))),
            }
        audit_event(cwd, kind, "approval_required", {"target": target})
        gate = autonomy_evaluate(
            cwd,
            action=f"browser action {target.get('action', '')}",
            blast_radius="service",
            reversible=True,
            evidence_count=8,
            contradictory_signals=0,
            independent_verifiers=2,
            checks={"browser_session": True, "verification_ready": True, "rollback_ready": True},
        )
        approval = request_approval(cwd, "browser_action", "interactive_browser_action_requires_approval", {"target": target, "gate": gate})
        return {"ok": False, "kind": kind, "reason": "approval_required", "gate": gate, "approval": approval}
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
            audit_event(cwd, kind, "approval_required", {"target": target})
            approval = request_approval(cwd, "store_install", "policy_requires_approval", {"target": target})
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
        )
        if gate.get("decision") != "allow":
            return {"ok": False, "kind": kind, "reason": "autonomy_gate", "gate": gate}
        return {"ok": True, "kind": kind, "result": store_install(cwd, str(target), "")}
    if kind == "self_repair":
        if policy["decision"] == "approval_required":
            audit_event(cwd, kind, "approval_required", {"target": target})
            approval = request_approval(cwd, "self_repair", "policy_requires_approval", {"target": target})
            return {"ok": False, "kind": kind, "reason": "approval_required", "approval": approval}
        gate = autonomy_evaluate(
            cwd,
            action="self repair run",
            blast_radius="system",
            reversible=True,
            evidence_count=10,
            contradictory_signals=0,
            independent_verifiers=3,
            checks={"runtime_ready": True, "rollback_ready": True, "verification_ready": True},
        )
        if gate.get("decision") != "allow":
            return {"ok": False, "kind": kind, "reason": "autonomy_gate", "gate": gate}
        return {"ok": True, "kind": kind, "result": run_self_repair(cwd)}
    if kind == "recover":
        if policy["decision"] == "approval_required":
            audit_event(cwd, kind, "approval_required", {"target": target})
            approval = request_approval(cwd, "recover", "policy_requires_approval", {"target": target})
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
        )
        if gate.get("decision") != "allow":
            return {"ok": False, "kind": kind, "reason": "autonomy_gate", "gate": gate}
        return {"ok": True, "kind": kind, "result": run_recovery(cwd)}
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
            ),
        }
    return {"ok": False, "kind": kind, "reason": "unknown_step"}
