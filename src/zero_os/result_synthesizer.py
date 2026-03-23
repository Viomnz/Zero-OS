from __future__ import annotations


def synthesize_result(run: dict) -> dict:
    lines = []
    contradiction_gate = dict(run.get("contradiction_gate") or {})
    if contradiction_gate.get("decision") == "hold":
        return {
            "summary": contradiction_gate.get("boundary_summary", "contradiction gate: hold"),
            "ok": False,
            "contradiction_gate": contradiction_gate,
        }
    if not run.get("results"):
        return {"summary": "No action was taken.", "ok": False, "contradiction_gate": contradiction_gate}
    replan = dict(run.get("replan") or {})
    if bool(replan.get("applied", False)):
        lines.append(f"replan: switched to {replan.get('candidate_branch_id', 'alternate')} after {replan.get('trigger', 'failure')}")
    for item in run["results"]:
        kind = item.get("kind", "step")
        if item.get("skipped", False) and str(item.get("reason", "")) == "conditional_not_triggered":
            continue
        if item.get("handled_by_fallback", False):
            lines.append(f"{kind}: failed, then continued through conditional fallback")
            continue
        if not item.get("ok", False):
            lines.append(f"{kind}: failed")
            continue
        result = item.get("result", {})
        if kind == "web_verify":
            lines.append(f"web verification: verified={result.get('verified', False)}")
        elif kind == "web_fetch":
            lines.append(f"web fetch: status={result.get('status', 0)}")
        elif kind == "store_status":
            lines.append(f"native store: ok={result.get('ok', False)}")
        elif kind == "recover":
            lines.append(f"recovery: ok={result.get('ok', False)}")
        elif kind == "self_repair":
            lines.append(f"self repair: ok={result.get('ok', False)}")
        elif kind == "browser_open":
            lines.append(f"browser open: opened={result.get('opened', False)}")
        elif kind == "browser_status":
            lines.append(f"browser session: tabs={len(result.get('tabs', []))}")
        elif kind == "browser_dom_inspect":
            lines.append(f"browser dom: selectors={len(result.get('page', {}).get('selectors', []))}")
        elif kind == "browser_action":
            suffix = f" via fallback from {item.get('conditional_triggered_by', '')}" if item.get("conditional_triggered_by") else ""
            lines.append(f"browser action: {'ok' if item.get('ok', False) else 'approval required'}{suffix}")
        elif item.get("condition_type") in {"on_success", "on_verified"}:
            lines.append(f"{kind}: ok via conditional {item.get('condition_type')}")
        elif kind == "api_request":
            lines.append(f"api request: status={result.get('status', 0)}")
        elif kind == "api_workflow":
            lines.append(f"api workflow: ok={result.get('ok', False)}")
        elif kind == "github_connect":
            lines.append(f"github connect: ok={result.get('ok', False)}")
        elif kind == "github_issues":
            lines.append(f"github issues: count={len(result.get('issues', []))}")
        elif kind == "cloud_target_set":
            lines.append(f"cloud target: ok={result.get('ok', False)}")
        elif kind == "cloud_deploy":
            lines.append(f"cloud deploy: ok={result.get('ok', False)}")
        elif kind == "autonomy_gate":
            lines.append(f"autonomy gate: {result.get('decision', 'unknown')}")
        elif kind == "flow_monitor":
            lines.append(f"flow monitor: score={result.get('flow_score', 0.0)}")
        elif kind == "smart_workspace":
            lines.append(f"smart workspace: indexed={result.get('indexed', False)}")
        elif kind == "maintenance_orchestrator":
            next_action = dict(result.get("next_action") or {})
            lines.append(f"maintenance orchestrator: next={next_action.get('action', 'observe')}")
        elif kind == "internet_capability":
            lines.append(f"internet capability: ready={result.get('internet_ready', result.get('summary', {}).get('internet_ready', False))}")
        elif kind == "world_class_readiness":
            lines.append(f"world class readiness: score={result.get('overall_score', 0.0)} grade={result.get('grade', 'F')}")
        elif kind == "contradiction_engine":
            lines.append(f"contradiction gate: {result.get('last_decision', result.get('decision', 'unknown'))}")
        elif kind == "pressure_harness":
            lines.append(f"pressure harness: score={result.get('overall_score', 0.0)}")
        elif kind == "controller_registry":
            lines.append(f"controller registry: subsystems={result.get('subsystem_count', 0)}")
        elif kind == "capability_expansion_protocol":
            lines.append("capability_expansion_protocol: ok")
        elif kind == "general_agent":
            lines.append("general agent: ok")
        elif kind == "domain_pack_generate_feature":
            lines.append("feature generator: ok")
        elif kind == "highway_dispatch":
            lines.append(f"highway: {result.get('capability', 'unknown')}")
        else:
            lines.append(f"{kind}: ok")
    return {"ok": run.get("ok", False), "summary": "\n".join(lines), "contradiction_gate": contradiction_gate}
