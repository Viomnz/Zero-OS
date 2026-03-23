from __future__ import annotations

from collections import defaultdict
from typing import Any


_ROLE_ALIASES = {
    "get": "retrieve",
    "retrieve": "retrieve",
    "fetch": "retrieve",
    "load": "retrieve",
    "read": "inspect",
    "check": "inspect",
    "verify": "inspect",
    "inspect": "inspect",
    "status": "inspect",
    "health": "inspect",
    "show": "present",
    "display": "present",
    "output": "present",
    "open": "initiate",
    "launch": "initiate",
    "start": "initiate",
    "click": "mutate",
    "submit": "mutate",
    "input": "mutate",
    "type": "mutate",
    "deploy": "deploy",
    "install": "install",
    "configure": "configure",
    "set": "configure",
    "plan": "plan",
    "reply": "respond",
    "post": "respond",
    "comment": "respond",
    "act": "mutate",
    "repair": "remediate",
    "fix": "remediate",
    "recover": "remediate",
    "recovery": "remediate",
    "repairing": "remediate",
}

_ROLE_PRIORITY = {
    "inspect": 0,
    "retrieve": 1,
    "present": 2,
    "configure": 3,
    "initiate": 4,
    "deploy": 5,
    "install": 6,
    "respond": 7,
    "mutate": 8,
    "remediate": 9,
    "plan": 10,
}

_TARGET_FAMILY_ALIASES = {
    "urls": "remote_source",
    "api_requests": "remote_source",
    "api_workflows": "remote_source",
    "files": "workspace_source",
    "file_ranges": "workspace_source",
    "commands": "workspace_source",
    "artifacts": "workspace_source",
    "repos": "collaboration_source",
    "issue_reads": "collaboration_source",
    "issue_comments": "collaboration_source",
    "issue_plans": "collaboration_source",
    "issue_actions": "collaboration_source",
    "issue_reply_drafts": "collaboration_source",
    "issue_reply_posts": "collaboration_source",
    "pr_reads": "collaboration_source",
    "pr_comments": "collaboration_source",
    "pr_plans": "collaboration_source",
    "pr_actions": "collaboration_source",
    "pr_reply_drafts": "collaboration_source",
    "pr_reply_posts": "collaboration_source",
    "cloud_targets": "delivery_surface",
    "deployments": "delivery_surface",
    "apps": "install_surface",
    "actions": "interaction_surface",
}


def _normalize_role(token: str) -> str:
    return _ROLE_ALIASES.get(str(token or "").strip().lower(), "")


def _target_families(targets: dict[str, Any]) -> list[str]:
    families: list[str] = []
    seen: set[str] = set()
    for item in list(dict(targets or {}).get("items", [])):
        target_type = str(item.get("type", "")).strip()
        family = _TARGET_FAMILY_ALIASES.get(target_type, "")
        if family and family not in seen:
            seen.add(family)
            families.append(family)
    return sorted(families)


def semantic_action_roles(text: str, decomposition: list[dict[str, Any]] | None = None) -> list[str]:
    roles: list[str] = []
    seen: set[str] = set()
    for subgoal in list(decomposition or []):
        for action in list(subgoal.get("action_hints", [])):
            role = _normalize_role(str(action))
            if role and role not in seen:
                seen.add(role)
                roles.append(role)
    lowered = str(text or "").lower()
    for token, role in _ROLE_ALIASES.items():
        if f" {token} " in f" {lowered} " and role not in seen:
            seen.add(role)
            roles.append(role)
    return sorted(roles, key=lambda role: (_ROLE_PRIORITY.get(role, 99), role))


def semantic_goal(text: str, targets: dict[str, Any], decomposition: list[dict[str, Any]] | None = None) -> str:
    roles = semantic_action_roles(text, decomposition)
    target_types = {str(item.get("type", "")) for item in list(dict(targets or {}).get("items", [])) if str(item.get("type", ""))}
    role_set = set(roles)
    if "deploy" in role_set or "configure" in role_set:
        return "configure_execute_release"
    if "respond" in role_set:
        return "coordinate_external_work"
    if "remediate" in role_set:
        return "repair_or_recover_system"
    if {"inspect", "retrieve", "present"} <= role_set:
        return "retrieve_and_present_information"
    if {"retrieve", "mutate"} <= role_set:
        return "inspect_then_mutate_resource"
    if {"inspect", "mutate"} <= role_set or {"present", "mutate"} <= role_set:
        return "inspect_then_mutate_resource"
    if "mutate" in role_set or "initiate" in role_set:
        return "mutate_resource"
    if "inspect" in role_set or "retrieve" in role_set or "present" in role_set:
        return "inspect_resource"
    if "repos" in target_types:
        return "coordinate_external_work"
    if "urls" in target_types:
        return "inspect_resource"
    return "observe_state"


def semantic_abstraction_profile(
    text: str,
    targets: dict[str, Any],
    decomposition: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    roles = semantic_action_roles(text, decomposition)
    role_set = set(roles)
    target_families = _target_families(targets)

    structure_family = "observation_pattern"
    if role_set & {"deploy", "configure"}:
        structure_family = "configure_release_pattern"
    elif role_set & {"respond", "plan"}:
        structure_family = "review_coordinate_pattern"
    elif role_set & {"remediate"}:
        structure_family = "observe_repair_pattern"
    elif role_set & {"mutate", "initiate"} and role_set & {"inspect", "retrieve", "present"}:
        structure_family = "verify_then_mutate_pattern"
    elif role_set & {"mutate", "initiate"}:
        structure_family = "control_mutation_pattern"
    elif role_set & {"inspect", "retrieve", "present"}:
        structure_family = "source_observation_pattern"

    analogies: list[str] = []
    if set(target_families) & {"remote_source", "workspace_source", "collaboration_source"}:
        analogies.append("source_retrieval_equivalence")
        analogies.append("fetch_surface_equivalence")
    if "interaction_surface" in target_families and structure_family in {"verify_then_mutate_pattern", "control_mutation_pattern"}:
        analogies.append("interactive_surface_control")
        analogies.append("state_change_equivalence")
    if "delivery_surface" in target_families and structure_family == "configure_release_pattern":
        analogies.append("delivery_pipeline_equivalence")
    if "delivery_surface" in target_families and "workspace_source" in target_families:
        analogies.append("artifact_delivery_equivalence")
    if "install_surface" in target_families and structure_family == "control_mutation_pattern":
        analogies.append("install_control_equivalence")
    if "install_surface" in target_families and "delivery_surface" in target_families:
        analogies.append("provisioning_pipeline_equivalence")
    if "collaboration_source" in target_families and role_set & {"respond", "plan"}:
        analogies.append("review_feedback_equivalence")
    if "remote_source" in target_families and "workspace_source" in target_families:
        analogies.append("source_bridge_equivalence")
    if "remote_source" in target_families and "interaction_surface" in target_families and structure_family in {"verify_then_mutate_pattern", "source_observation_pattern", "control_mutation_pattern"}:
        analogies.append("browser_fetch_equivalence")
    if "workspace_source" in target_families and structure_family in {"source_observation_pattern", "verify_then_mutate_pattern"}:
        analogies.append("file_fetch_equivalence")
    if "delivery_surface" in target_families and role_set & {"configure", "deploy"}:
        analogies.append("deploy_control_equivalence")

    return {
        "roles": roles,
        "target_families": target_families,
        "structure_family": structure_family,
        "semantic_goal": semantic_goal(text, targets, decomposition),
        "analogies": analogies,
    }


def generate_semantic_interpretations(
    request: str,
    decomposition: list[dict[str, Any]],
    targets: dict[str, Any],
    *,
    limit: int = 16,
) -> list[dict[str, Any]]:
    abstraction = semantic_abstraction_profile(request, targets, decomposition)
    roles = list(abstraction.get("roles", []))
    role_set = set(roles)
    target_types = sorted({str(item.get("type", "")) for item in list(dict(targets or {}).get("items", [])) if str(item.get("type", ""))})
    goal = str(abstraction.get("semantic_goal", semantic_goal(request, targets, decomposition)))
    target_families = list(abstraction.get("target_families", []))
    structure_family = str(abstraction.get("structure_family", "observation_pattern"))
    analogies = set(str(item) for item in list(abstraction.get("analogies", [])) if str(item))
    request_shape = "multi_step" if len(list(decomposition or [])) > 1 else "single_step"
    interpretations: list[dict[str, Any]] = []
    seen: set[str] = set()

    def add(kind: str, structure: list[str], confidence: float, note: str) -> None:
        payload = {
            "kind": kind,
            "goal": goal,
            "structure": [role for role in structure if role],
            "target_types": target_types,
            "target_families": target_families,
            "abstraction_family": structure_family,
            "request_shape": request_shape,
            "confidence": round(max(0.0, min(1.0, confidence)), 3),
            "note": note,
        }
        signature = f"{payload['goal']}|{'->'.join(payload['structure'])}|{','.join(payload['target_types'])}|{kind}"
        if signature in seen:
            return
        seen.add(signature)
        interpretations.append(payload)

    add("canonical", roles or ["inspect"], 0.94, "Semantic interpretation normalized from phrasing and subgoal actions.")
    if roles:
        add("minimal_goal", roles[:2], 0.72, "Minimal semantic structure that keeps only the strongest roles.")
        add("full_goal", roles + [role for role in ("inspect", "present") if role not in role_set], 0.66, "Full semantic interpretation preserving more explicit stages.")
    if {"inspect", "mutate"} <= role_set or {"present", "mutate"} <= role_set:
        add("verification_first", ["inspect", "retrieve", "initiate", "mutate"], 0.81, "Observation-before-mutation interpretation for mixed requests.")
    if "retrieve" in role_set and "present" not in role_set:
        add("retrieval_only", ["retrieve"], 0.63, "Pure retrieval interpretation shared across phrasing like get/retrieve/load.")
        add("retrieval_then_present", ["retrieve", "present"], 0.69, "Retrieval plus presentation interpretation for information requests.")
    if "inspect" in role_set and "present" in role_set:
        add("inspect_then_present", ["inspect", "present"], 0.74, "Inspection plus presentation interpretation.")
    if "deploy" in role_set or "configure" in role_set:
        add("deployment_pipeline", ["inspect", "configure", "deploy", "present"], 0.76, "Deployment pipeline interpretation with setup and verification stages.")
    if "remediate" in role_set:
        add("guarded_remediation", ["inspect", "remediate", "inspect"], 0.78, "Guarded remediation interpretation with verification on both sides.")
    if len(target_types) > 1:
        add("target_isolated", ["inspect", "present", "mutate"], 0.67, "Interpretation that isolates mixed targets before mutation.")
    if any(bool(item.get("conditional", False)) for item in list(decomposition or [])):
        add("conditional_flow", ["inspect", "mutate", "inspect"], 0.71, "Conditional interpretation that preserves verification around branch changes.")
    if len(list(decomposition or [])) > 2:
        add("multi_stage_chain", ["inspect", "retrieve", "prepare", "mutate", "present"], 0.64, "Multi-stage interpretation for longer reasoning chains.")
    if role_set <= {"inspect", "retrieve", "present"}:
        add("read_only_observation", ["inspect", "retrieve", "present"], 0.8, "Read-only semantic interpretation with no mutation.")
    if "mutate" in role_set and "inspect" not in role_set:
        add("direct_mutation", ["initiate", "mutate", "inspect"], 0.62, "Direct mutation interpretation with post-action verification.")
    if "respond" in role_set:
        add("response_workflow", ["inspect", "plan", "respond"], 0.74, "Response workflow interpretation for GitHub and external coordination.")
    if structure_family == "source_observation_pattern":
        add("cross_domain_source_observation", ["inspect", "retrieve", "present"], 0.77, "Cross-domain source observation abstraction shared across remote, workspace, and collaboration sources.")
    if structure_family == "verify_then_mutate_pattern":
        add("cross_domain_verify_then_mutate", ["inspect", "retrieve", "mutate", "inspect"], 0.73, "Cross-domain verify-then-mutate abstraction reused across browser and control surfaces.")
    if structure_family == "configure_release_pattern":
        add("cross_domain_release_pipeline", ["inspect", "configure", "deploy", "present"], 0.72, "Cross-domain release pipeline abstraction for deployment-like requests.")
    add("causal_probe", [roles[0] if roles else "inspect", "inspect", roles[-1] if roles else "present"], 0.58, "Interpretation that inserts verification to probe causal dependencies.")
    add("uncertainty_guarded", ["inspect", "retrieve", "present"], 0.56, "Interpretation that keeps uncertainty low through retrieval and presentation first.")
    add("counterfactual", list(reversed(roles or ["inspect"])), 0.52, "Counterfactual semantic interpretation used to challenge the canonical reading.")
    add("target_focused", [role for role in (["inspect"] + roles[:2]) if role], 0.54, "Target-focused interpretation that compresses the request into the most target-relevant roles.")
    add("resource_limited", [role for role in (roles[:1] + ["inspect", "present"]) if role], 0.53, "Resource-limited interpretation that keeps only the most defensible stages.")
    add("failure_ready", [role for role in (["inspect"] + roles[:1] + ["inspect"]) if role], 0.57, "Failure-ready interpretation that keeps verification wrapped around the primary action.")
    add("edge_case_sparse", [roles[0] if roles else "inspect", "present"], 0.5, "Sparse interpretation for incomplete-input or missing-context conditions.")
    if target_types:
        add("target_type_projection", ["inspect", "retrieve", target_types[0]], 0.49, "Projection that emphasizes the dominant target family during interpretation.")
    if "initiate" in role_set:
        add("initiate_then_inspect", ["initiate", "inspect", "present"], 0.55, "Interpretation that opens a resource first, then validates and reports state.")
    if "mutate" in role_set:
        add("mutation_probe", ["inspect", "mutate", "present"], 0.59, "Interpretation that treats mutation as something to probe and then report.")
    if {"inspect", "mutate"} <= role_set or {"retrieve", "mutate"} <= role_set:
        add("verification_guarded_mutation", ["inspect", "retrieve", "mutate", "inspect"], 0.68, "Interpretation that forces a verification envelope around mutation.")

    interpretations.sort(key=lambda item: (-float(item.get("confidence", 0.0) or 0.0), item.get("kind", "")))
    return interpretations[: max(10, limit)]


def semantic_intent_votes(
    request: str,
    targets: dict[str, Any],
    decomposition: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    abstraction = semantic_abstraction_profile(request, targets, decomposition)
    roles = list(abstraction.get("roles", []))
    goal = str(abstraction.get("semantic_goal", semantic_goal(request, targets, decomposition)))
    votes: defaultdict[str, float] = defaultdict(float)
    reasons: defaultdict[str, list[str]] = defaultdict(list)
    target_types = {str(item.get("type", "")) for item in list(dict(targets or {}).get("items", [])) if str(item.get("type", ""))}
    target_families = set(str(item) for item in list(abstraction.get("target_families", [])) if str(item))
    structure_family = str(abstraction.get("structure_family", "observation_pattern"))
    analogies = set(str(item) for item in list(abstraction.get("analogies", [])) if str(item))

    def bump(intent_name: str, weight: float, reason: str) -> None:
        votes[intent_name] += weight
        reasons[intent_name].append(reason)

    role_set = set(roles)
    lowered = str(request or "").lower()
    if "urls" in target_types and role_set & {"inspect", "retrieve", "present"}:
        bump("web", 0.7, "semantic_web_observation")
    if "urls" in target_types and role_set & {"initiate", "mutate"}:
        bump("browser", 0.75, "semantic_browser_mutation")
        bump("web", 0.45, "semantic_web_mutation_support")
    if "browser" in lowered:
        bump("browser", 0.35, "semantic_browser_channel")
        if "status" in lowered or role_set & {"inspect", "retrieve", "present"}:
            bump("browser", 0.18, "semantic_browser_observation_channel")
            bump("web", 0.12, "semantic_browser_observation")
        if "urls" in target_types:
            bump("browser", 0.18, "semantic_browser_url_channel")
    if target_types & {"files", "file_ranges"} and role_set & {"inspect", "retrieve", "present"}:
        bump("highway", 0.55, "semantic_file_observation")
    if structure_family == "source_observation_pattern":
        if "remote_source" in target_families:
            bump("web", 0.18, "semantic_abstraction_remote_source")
        if "workspace_source" in target_families:
            bump("highway", 0.18, "semantic_abstraction_workspace_source")
        if "collaboration_source" in target_families:
            bump("github", 0.18, "semantic_abstraction_collaboration_source")
    if structure_family == "verify_then_mutate_pattern" and "remote_source" in target_families:
        bump("browser", 0.2, "semantic_abstraction_verify_then_mutate")
        bump("web", 0.12, "semantic_abstraction_verify_then_mutate_support")
    if "fetch_surface_equivalence" in analogies:
        if "remote_source" in target_families:
            bump("web", 0.12, "semantic_fetch_surface_equivalence")
        if "workspace_source" in target_families:
            bump("highway", 0.12, "semantic_fetch_surface_equivalence")
    if "browser_fetch_equivalence" in analogies:
        bump("browser", 0.14, "semantic_browser_fetch_equivalence")
    if "file_fetch_equivalence" in analogies:
        bump("highway", 0.14, "semantic_file_fetch_equivalence")
    if "deploy_control_equivalence" in analogies or "delivery_pipeline_equivalence" in analogies:
        bump("cloud", 0.14, "semantic_delivery_equivalence")
    if "review_feedback_equivalence" in analogies:
        bump("github", 0.14, "semantic_review_feedback_equivalence")
    if target_types & {"deployments", "cloud_targets", "artifacts"} and role_set & {"configure", "deploy"}:
        bump("cloud", 0.8, "semantic_cloud_pipeline")
    if target_types & {"repos", "issue_reads", "issue_comments", "issue_plans", "issue_actions", "issue_reply_drafts", "issue_reply_posts", "pr_reads", "pr_comments", "pr_plans", "pr_actions", "pr_reply_drafts", "pr_reply_posts"}:
        bump("github", 0.75, "semantic_github_target")
    if "apps" in target_types and ("install" in role_set or "mutate" in role_set):
        bump("store_install", 0.7, "semantic_install_request")
    if role_set & {"remediate"}:
        lowered = str(request or "").lower()
        if "recover" in lowered or "recovery" in lowered:
            bump("recover", 0.85, "semantic_recovery")
        if "repair" in lowered or "fix" in lowered:
            bump("self_repair", 0.85, "semantic_self_repair")
    if goal in {"retrieve_and_present_information", "inspect_resource"}:
        bump("status", 0.35, "semantic_information_request")
    if "api_requests" in target_types or "api_workflows" in target_types:
        bump("api", 0.7, "semantic_api_request")
    return {
        "roles": roles,
        "goal": goal,
        "abstraction": abstraction,
        "votes": {str(key): round(float(value), 3) for key, value in votes.items()},
        "reasons": {str(key): list(value) for key, value in reasons.items()},
    }
