from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MutationClass:
    name: str
    risk: str
    required_scope: str
    requires_rollback: bool = True
    external_side_effect: bool = False


MUTATION_CLASSES: dict[str, MutationClass] = {
    "code_change": MutationClass("code_change", "high", "codebase:mutation", True),
    "self_repair": MutationClass("self_repair", "high", "runtime:self_repair", True),
    "recover": MutationClass("recover", "high", "runtime:recovery", True),
    "store_install": MutationClass("store_install", "high", "software:install", True),
    "browser_action": MutationClass("browser_action", "high", "browser:mutation", True, True),
    "cloud_deploy": MutationClass("cloud_deploy", "critical", "cloud:deploy", True, True),
    "cloud_target_set": MutationClass("cloud_target_set", "high", "cloud:configure", True, True),
    "github_issue_act": MutationClass("github_issue_act", "high", "github:issue_action", True, True),
    "github_pr_act": MutationClass("github_pr_act", "high", "github:pr_action", True, True),
    "github_issue_reply_post": MutationClass("github_issue_reply_post", "high", "github:issue_write", False, True),
    "github_pr_reply_post": MutationClass("github_pr_reply_post", "high", "github:pr_write", False, True),
    "api_request_mutation": MutationClass("api_request_mutation", "high", "api:mutation", True, True),
    "api_workflow_mutation": MutationClass("api_workflow_mutation", "high", "api:workflow_mutation", True, True),
    "self_upgrade": MutationClass("self_upgrade", "critical", "zero_os:self_upgrade", True),
    "policy_change": MutationClass("policy_change", "critical", "authority:policy_change", True),
    "authority_change": MutationClass("authority_change", "critical", "authority:change", True),
    "credential_change": MutationClass("credential_change", "critical", "credential:change", True, True),
}


ALIASES: dict[str, str] = {
    "github_issue_reply": "github_issue_reply_post",
    "github_pr_reply": "github_pr_reply_post",
    "zero_ai_upgrade_system": "self_upgrade",
    "zero_ai_self_upgrade": "self_upgrade",
    "run_code_fix_loop": "code_change",
    "run_code_canary": "code_change",
}


def canonical_mutation_kind(kind: str) -> str:
    normalized = str(kind or "").strip().lower()
    return ALIASES.get(normalized, normalized)


def mutation_class(kind: str) -> MutationClass | None:
    return MUTATION_CLASSES.get(canonical_mutation_kind(kind))


def is_known_mutation(kind: str) -> bool:
    return mutation_class(kind) is not None
