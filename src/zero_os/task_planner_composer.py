from __future__ import annotations

import re
from typing import Any

from zero_os.code_task_lane import parse_code_instruction
from zero_os.task_planner_parsing import _build_browser_action_target
from zero_os.task_planner_policy import (
    MUTATION_TOKENS,
    _APPROVAL_POSSIBLE_KINDS,
    _EXCLUSIVE_PATTERNS,
    _HIGH_RISK_REMEDIATION_KINDS,
    _MUTATING_STEP_KINDS,
    _VERIFICATION_PRIORITY_KINDS,
)


def risk_level_for_kind(kind: str) -> str:
    if kind in {"recover", "self_repair", "cloud_deploy", "store_install", "code_change"}:
        return "high"
    if kind in {"browser_action", "browser_open", "github_issue_act", "github_issue_reply_post", "github_pr_act", "github_pr_reply_post"}:
        return "medium"
    return "low"


def verification_mode_for_kind(kind: str) -> str:
    if kind in _VERIFICATION_PRIORITY_KINDS:
        return "observe"
    if kind in {"browser_action", "browser_open", "cloud_deploy", "recover", "self_repair", "store_install", "code_change"}:
        return "post_action_verification"
    if kind == "autonomy_gate":
        return "gate_only"
    return "standard"


def step_allows_mutation(kind: str) -> bool:
    return kind in _MUTATING_STEP_KINDS


def make_step(
    kind: str,
    target: Any,
    *,
    subgoal_id: str,
    route_confidence: float,
    source_of_route: str,
    attached_targets: list[str] | None = None,
    justification: str = "",
    mutation_requested_explicitly: bool | None = None,
    mutation_justification: str = "",
) -> dict[str, Any]:
    allows_mutation = step_allows_mutation(kind)
    explicit_mutation = bool(mutation_requested_explicitly) if mutation_requested_explicitly is not None else False
    effective_mutation_justification = mutation_justification or justification if allows_mutation else ""
    return {
        "kind": kind,
        "target": target,
        "risk_level": risk_level_for_kind(kind),
        "requires_approval_possible": kind in _APPROVAL_POSSIBLE_KINDS,
        "verification_mode": verification_mode_for_kind(kind),
        "source_of_route": source_of_route,
        "route_confidence": round(max(0.0, min(1.0, route_confidence)), 3),
        "confidence": round(max(0.0, min(1.0, route_confidence)), 3),
        "subgoal_id": subgoal_id,
        "attached_targets": list(attached_targets or []),
        "justification": justification or source_of_route,
        "mutation_requested_explicitly": explicit_mutation if allows_mutation else False,
        "mutation_justification": effective_mutation_justification,
        "mutation_allowed_with_justification": bool(allows_mutation and explicit_mutation and effective_mutation_justification),
        "preconditions": [],
        "precondition_issues": [],
        "precondition_state": "ready",
    }


def compose_primary_steps(
    text: str,
    lowered: str,
    targets: dict[str, Any],
    resolved: dict[str, Any],
    *,
    remembered_plan: dict[str, Any] | None = None,
    initial_ambiguity_flags: list[str] | None = None,
) -> dict[str, Any]:
    steps: list[dict[str, Any]] = []
    ambiguity_flags = list(initial_ambiguity_flags or [])
    primary_confidence = max(float(resolved.get("primary_confidence", 0.0) or 0.0), 0.0)
    code_tokens = {"replace", "edit", "update", "modify", "refactor", "write", "change", "patch"}
    code_mutation_requested = any(token in lowered for token in code_tokens)
    code_instruction = parse_code_instruction(text) if code_mutation_requested else {"ok": False}

    remembered = dict(remembered_plan or {})
    if remembered.get("ok", False):
        for index, step in enumerate(list((remembered.get("plan") or {}).get("steps", []))):
            steps.append(
                make_step(
                    str(step.get("kind", "")),
                    step.get("target"),
                    subgoal_id=f"resume_{index}",
                    route_confidence=max(0.4, primary_confidence - 0.1),
                    source_of_route="resume_memory",
                    attached_targets=list(step.get("attached_targets", [])),
                )
            )

    exclusive_match = next((intent_name for intent_name, matcher in _EXCLUSIVE_PATTERNS if matcher(lowered)), "")
    if exclusive_match == "planning":
        steps.append(make_step("controller_registry", "highest_value_steps", subgoal_id="planning", route_confidence=1.0, source_of_route="exclusive:planning"))
    elif exclusive_match == "capability_expansion_protocol":
        steps.append(make_step("capability_expansion_protocol", "status", subgoal_id="capability_expansion_protocol", route_confidence=1.0, source_of_route="exclusive:capability_expansion_protocol"))
    elif exclusive_match == "general_agent":
        steps.append(make_step("general_agent", "status", subgoal_id="general_agent", route_confidence=1.0, source_of_route="exclusive:general_agent"))
    elif exclusive_match == "reasoning":
        steps.append(make_step("contradiction_engine", "status", subgoal_id="reasoning", route_confidence=1.0, source_of_route="exclusive:reasoning"))
    elif exclusive_match == "pressure":
        steps.append(make_step("pressure_harness", "run", subgoal_id="pressure", route_confidence=1.0, source_of_route="exclusive:pressure"))
    elif exclusive_match == "feature_generation":
        feature_value = str((targets.get("feature_requests") or [{"value": text[len("add feature "):].strip()}])[0]["value"])
        steps.append(
            make_step(
                "domain_pack_generate_feature",
                feature_value,
                subgoal_id="feature_generation",
                route_confidence=1.0,
                source_of_route="exclusive:feature_generation",
                attached_targets=[item["id"] for item in targets.get("feature_requests", [])],
            )
        )
        return {"steps": steps, "ambiguity_flags": list(dict.fromkeys(ambiguity_flags))}

    if any(token in lowered for token in ("tools", "capabilities", "what can you do")):
        steps.append(make_step("tool_registry", "registry", subgoal_id="tools", route_confidence=max(primary_confidence, 0.75), source_of_route="tools_phrase"))
    if "smart workspace" in lowered:
        steps.append(make_step("smart_workspace", "main", subgoal_id="workspace", route_confidence=max(primary_confidence, 0.8), source_of_route="workspace_phrase"))
    if "maintenance" in lowered and "domain pack" not in lowered:
        steps.append(make_step("maintenance_orchestrator", "status" if "status" in lowered else "main", subgoal_id="maintenance", route_confidence=max(primary_confidence, 0.8), source_of_route="maintenance_phrase"))
    if "world class" in lowered and "readiness" in lowered:
        steps.append(make_step("world_class_readiness", "status", subgoal_id="world_class", route_confidence=max(primary_confidence, 0.85), source_of_route="readiness_phrase"))
    if "internet" in lowered and not targets.get("urls") and "browser" not in lowered:
        steps.append(make_step("internet_capability", "status", subgoal_id="internet", route_confidence=max(primary_confidence, 0.8), source_of_route="internet_phrase"))
    if any(token in lowered for token in ("find contradiction", "bugs", "errors", "virus", "flow scan", "flow monitor", "malware")):
        steps.append(make_step("flow_monitor", ".", subgoal_id="flow_monitor", route_confidence=max(primary_confidence, 0.82), source_of_route="flow_phrase"))

    inspect_targets: list[tuple[str, list[str], str]] = []
    action_items = list(targets.get("actions", []))
    for item in list(targets.get("urls", [])):
        url = str(item["value"])
        attached = [item["id"]]
        steps.append(make_step("web_verify", url, subgoal_id=item["id"], route_confidence=max(primary_confidence, 0.85), source_of_route="explicit_url", attached_targets=attached))
        if any(token in lowered for token in ("fetch", "open", "read", "load")):
            steps.append(make_step("web_fetch", url, subgoal_id=item["id"], route_confidence=max(primary_confidence, 0.8), source_of_route="web_fetch_tokens", attached_targets=attached))
        if "open" in lowered:
            open_attached = attached + [str(action["id"]) for action in action_items if str(action.get("value", "")).strip().lower() == "open"]
            steps.append(
                make_step(
                    "browser_open",
                    url,
                    subgoal_id=item["id"],
                    route_confidence=max(primary_confidence, 0.78),
                    source_of_route="browser_open_tokens",
                    attached_targets=open_attached,
                    justification="Mutation requested explicitly through open language.",
                    mutation_requested_explicitly=True,
                    mutation_justification="Explicit open request on browser target.",
                )
            )
        action_target, action_issue = _build_browser_action_target(text, url)
        if action_issue:
            ambiguity_flags.append(action_issue)
        elif action_target:
            action_name = str(action_target.get("action", "")).strip().lower()
            matching_action_values = {"input", "type"} if action_name == "input" else {action_name}
            action_attached = attached + [
                str(action["id"])
                for action in action_items
                if str(action.get("value", "")).strip().lower() in matching_action_values
            ]
            steps.append(
                make_step(
                    "browser_action",
                    action_target,
                    subgoal_id=item["id"],
                    route_confidence=max(primary_confidence, 0.72),
                    source_of_route="browser_action_tokens",
                    attached_targets=action_attached,
                    justification="Mutation requested explicitly through browser action language.",
                    mutation_requested_explicitly=True,
                    mutation_justification=f"Explicit browser action request: {action_target.get('action', 'act')}.",
                )
            )
        if any(token in lowered for token in ("inspect page", "dom inspect")):
            inspect_targets.append((url, attached, item["id"]))

    if any(token in lowered for token in ("browser status", "tabs", "session")):
        steps.append(make_step("browser_status", "browser", subgoal_id="browser_status", route_confidence=max(primary_confidence, 0.8), source_of_route="browser_status_phrase"))
    for url, attached, item_id in inspect_targets:
        steps.append(make_step("browser_dom_inspect", url, subgoal_id=f"inspect_{item_id}", route_confidence=max(primary_confidence, 0.78), source_of_route="browser_inspect_tokens", attached_targets=attached))
    if ("status" in lowered or "diagnostic" in lowered or "health" in lowered or "check" in lowered) and not targets.get("urls"):
        if "contradiction status" not in lowered and "capability expansion protocol status" not in lowered and "world class readiness" not in lowered:
            steps.append(make_step("system_status", "health", subgoal_id="system_status", route_confidence=max(primary_confidence, 0.8), source_of_route="status_phrase"))
    if "native store status" in lowered or "store status" in lowered:
        steps.append(make_step("store_status", "native_store", subgoal_id="store_status", route_confidence=max(primary_confidence, 0.85), source_of_route="store_status_phrase"))
    for item in targets.get("apps", []):
        steps.append(
            make_step(
                "store_install",
                item["value"],
                subgoal_id=item["id"],
                route_confidence=max(primary_confidence, 0.88),
                source_of_route="install_app_target",
                attached_targets=[item["id"]],
                justification="Mutation requested explicitly through install app target.",
                mutation_requested_explicitly=True,
                mutation_justification="Explicit store install request with concrete app target.",
            )
        )
    file_items = list(targets.get("files", []))
    file_range_items = list(targets.get("file_ranges", []))
    if code_mutation_requested and (file_items or file_range_items):
        attached_targets = [str(item["id"]) for item in file_items] + [str(item["id"]) for item in file_range_items]
        steps.append(
            make_step(
                "code_change",
                {
                    "request": text,
                    "files": [str(item["value"]) for item in file_items],
                    "file_ranges": [dict(item["value"] or {}) for item in file_range_items],
                    "instruction": dict(code_instruction or {}),
                },
                subgoal_id="code_change",
                route_confidence=max(primary_confidence, 0.86 if bool(code_instruction.get("ok", False)) else 0.65),
                source_of_route="code_mutation_target",
                attached_targets=attached_targets,
                justification="Code mutation requested explicitly against scoped file targets.",
                mutation_requested_explicitly=True,
                mutation_justification="Explicit code-change request against file targets.",
            )
        )
        if not bool(code_instruction.get("ok", False)):
            ambiguity_flags.append("code_instruction_missing")
    else:
        for item in file_items:
            file_path = str(item["value"])
            file_command = f"read file {file_path}"
            if "show file" in lowered:
                file_command = f"show file {file_path}"
            elif "inspect file" in lowered:
                file_command = f"inspect file {file_path}"
            steps.append(make_step("highway_dispatch", file_command, subgoal_id=item["id"], route_confidence=max(primary_confidence, 0.74), source_of_route="file_target", attached_targets=[item["id"]]))
        for item in file_range_items:
            file_range = dict(item["value"] or {})
            range_command = f"show file {file_range.get('path', '')} lines {file_range.get('start_line', 0)}-{file_range.get('end_line', 0)}"
            steps.append(
                make_step(
                    "highway_dispatch",
                    range_command,
                    subgoal_id=item["id"],
                    route_confidence=max(primary_confidence, 0.76),
                    source_of_route="file_range_target",
                    attached_targets=[item["id"]],
                )
            )
    for item in targets.get("branches", []):
        branch_name = str(item["value"])
        steps.append(
            make_step(
                "highway_dispatch",
                f"show branch {branch_name}",
                subgoal_id=item["id"],
                route_confidence=max(primary_confidence, 0.7),
                source_of_route="branch_target",
                attached_targets=[item["id"]],
            )
        )
    deployment_artifacts = {str(item["value"].get("artifact", "")) for item in targets.get("deployments", [])}
    for item in targets.get("artifacts", []):
        artifact_name = str(item["value"])
        if artifact_name in deployment_artifacts:
            continue
        steps.append(
            make_step(
                "highway_dispatch",
                f"show artifact {artifact_name}",
                subgoal_id=item["id"],
                route_confidence=max(primary_confidence, 0.7),
                source_of_route="artifact_target",
                attached_targets=[item["id"]],
            )
        )
    if re.search(r"\bself repair\b", lowered):
        steps.append(
            make_step(
                "self_repair",
                "runtime",
                subgoal_id="self_repair",
                route_confidence=max(primary_confidence, 0.9),
                source_of_route="explicit_self_repair",
                justification="High-risk remediation explicitly requested.",
                mutation_requested_explicitly=True,
                mutation_justification="Explicit self-repair request on runtime scope.",
            )
        )
    if re.search(r"\brecover\b|\brecovery\b", lowered):
        steps.append(
            make_step(
                "recover",
                "runtime",
                subgoal_id="recover",
                route_confidence=max(primary_confidence, 0.9),
                source_of_route="explicit_recover",
                justification="High-risk recovery explicitly requested.",
                mutation_requested_explicitly=True,
                mutation_justification="Explicit recover request on runtime scope.",
            )
        )
    for item in targets.get("api_requests", []):
        steps.append(make_step("api_request", item["value"], subgoal_id=item["id"], route_confidence=max(primary_confidence, 0.82), source_of_route="api_request_target", attached_targets=[item["id"]]))
    for item in targets.get("api_workflows", []):
        if list(item["value"].get("paths", [])):
            steps.append(make_step("api_workflow", item["value"], subgoal_id=item["id"], route_confidence=max(primary_confidence, 0.8), source_of_route="api_workflow_target", attached_targets=[item["id"]]))
    for item in targets.get("repos", []):
        steps.append(make_step("github_connect", item["value"], subgoal_id=item["id"], route_confidence=max(primary_confidence, 0.8), source_of_route="github_connect_target", attached_targets=[item["id"]]))
    for item in targets.get("issue_reads", []):
        steps.append(make_step("github_issue_read", item["value"], subgoal_id=item["id"], route_confidence=max(primary_confidence, 0.78), source_of_route="github_issue_read_target", attached_targets=[item["id"]]))
    for item in targets.get("issue_comments", []):
        steps.append(make_step("github_issue_comments", item["value"], subgoal_id=item["id"], route_confidence=max(primary_confidence, 0.78), source_of_route="github_issue_comments_target", attached_targets=[item["id"]]))
    for item in targets.get("issue_plans", []):
        steps.append(make_step("github_issue_plan", item["value"], subgoal_id=item["id"], route_confidence=max(primary_confidence, 0.8), source_of_route="github_issue_plan_target", attached_targets=[item["id"]]))
    for item in targets.get("issue_actions", []):
        steps.append(
            make_step(
                "github_issue_act",
                item["value"],
                subgoal_id=item["id"],
                route_confidence=max(primary_confidence, 0.8),
                source_of_route="github_issue_act_target",
                attached_targets=[item["id"]],
                justification="GitHub issue action explicitly requested.",
                mutation_requested_explicitly=True,
                mutation_justification="Explicit GitHub issue action request.",
            )
        )
    for item in targets.get("issue_reply_drafts", []):
        steps.append(make_step("github_issue_reply_draft", item["value"], subgoal_id=item["id"], route_confidence=max(primary_confidence, 0.78), source_of_route="github_issue_reply_draft_target", attached_targets=[item["id"]]))
    for item in targets.get("issue_reply_posts", []):
        steps.append(
            make_step(
                "github_issue_reply_post",
                item["value"],
                subgoal_id=item["id"],
                route_confidence=max(primary_confidence, 0.82),
                source_of_route="github_issue_reply_post_target",
                attached_targets=[item["id"]],
                justification="GitHub issue reply post explicitly requested.",
                mutation_requested_explicitly=True,
                mutation_justification="Explicit GitHub issue reply post request.",
            )
        )
    for item in targets.get("pr_reads", []):
        steps.append(make_step("github_pr_read", item["value"], subgoal_id=item["id"], route_confidence=max(primary_confidence, 0.78), source_of_route="github_pr_read_target", attached_targets=[item["id"]]))
    for item in targets.get("pr_comments", []):
        steps.append(make_step("github_pr_comments", item["value"], subgoal_id=item["id"], route_confidence=max(primary_confidence, 0.78), source_of_route="github_pr_comments_target", attached_targets=[item["id"]]))
    for item in targets.get("pr_plans", []):
        steps.append(make_step("github_pr_plan", item["value"], subgoal_id=item["id"], route_confidence=max(primary_confidence, 0.8), source_of_route="github_pr_plan_target", attached_targets=[item["id"]]))
    for item in targets.get("pr_actions", []):
        steps.append(
            make_step(
                "github_pr_act",
                item["value"],
                subgoal_id=item["id"],
                route_confidence=max(primary_confidence, 0.8),
                source_of_route="github_pr_act_target",
                attached_targets=[item["id"]],
                justification="GitHub pull request action explicitly requested.",
                mutation_requested_explicitly=True,
                mutation_justification="Explicit GitHub pull request action request.",
            )
        )
    for item in targets.get("pr_reply_drafts", []):
        steps.append(make_step("github_pr_reply_draft", item["value"], subgoal_id=item["id"], route_confidence=max(primary_confidence, 0.78), source_of_route="github_pr_reply_draft_target", attached_targets=[item["id"]]))
    for item in targets.get("pr_reply_posts", []):
        steps.append(
            make_step(
                "github_pr_reply_post",
                item["value"],
                subgoal_id=item["id"],
                route_confidence=max(primary_confidence, 0.82),
                source_of_route="github_pr_reply_post_target",
                attached_targets=[item["id"]],
                justification="GitHub pull request reply post explicitly requested.",
                mutation_requested_explicitly=True,
                mutation_justification="Explicit GitHub pull request reply post request.",
            )
        )
    for item in targets.get("cloud_targets", []):
        steps.append(make_step("cloud_target_set", item["value"], subgoal_id=item["id"], route_confidence=max(primary_confidence, 0.8), source_of_route="cloud_target_phrase", attached_targets=[item["id"]]))
    for item in targets.get("deployments", []):
        artifact_attached = [
            str(artifact["id"])
            for artifact in targets.get("artifacts", [])
            if str(artifact.get("value", "")).strip() == str(item["value"].get("artifact", "")).strip()
        ]
        steps.append(
            make_step(
                "cloud_deploy",
                item["value"],
                subgoal_id=item["id"],
                route_confidence=max(primary_confidence, 0.84),
                source_of_route="cloud_deploy_phrase",
                attached_targets=[item["id"], *artifact_attached],
                justification="Mutation requested explicitly through deploy target.",
                mutation_requested_explicitly=True,
                mutation_justification="Explicit deploy request with artifact and target.",
            )
        )
    for item in targets.get("commands", []):
        steps.append(make_step("highway_dispatch", item["value"], subgoal_id=item["id"], route_confidence=max(primary_confidence, 0.72), source_of_route="command_target", attached_targets=[item["id"]]))
    if any(token in lowered for token in ("fix", "repair", "recover")):
        steps.append(make_step("autonomy_gate", text, subgoal_id="autonomy_gate", route_confidence=max(primary_confidence, 0.7), source_of_route="remediation_gate"))

    return {"steps": steps, "ambiguity_flags": list(dict.fromkeys(ambiguity_flags))}
