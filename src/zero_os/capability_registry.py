from __future__ import annotations

from dataclasses import dataclass

from zero_os.mutation_registry import mutation_class


@dataclass(frozen=True)
class CapabilityClass:
    name: str
    mode: str
    risk: str
    required_scope: str
    sensitive: bool = False
    external_side_effect: bool = False
    mutation_kind: str = ""


CAPABILITY_CLASSES: dict[str, CapabilityClass] = {
    "observe": CapabilityClass("observe", "read", "low", "runtime:observe"),
    "system_status": CapabilityClass("system_status", "read", "low", "runtime:status"),
    "tool_registry": CapabilityClass("tool_registry", "read", "low", "tools:enumerate"),
    "controller_registry": CapabilityClass("controller_registry", "read", "low", "controllers:enumerate"),
    "browser_status": CapabilityClass("browser_status", "read", "low", "browser:status"),
    "browser_dom_inspect": CapabilityClass("browser_dom_inspect", "read", "medium", "browser:inspect", True),
    "web_verify": CapabilityClass("web_verify", "network_read", "medium", "network:verify", True, True),
    "web_fetch": CapabilityClass("web_fetch", "network_read", "medium", "network:fetch", True, True),
    "store_status": CapabilityClass("store_status", "read", "low", "software:status"),
    "api_request": CapabilityClass("api_request", "network_read", "high", "api:read", True, True),
    "api_workflow": CapabilityClass("api_workflow", "network_read", "high", "api:workflow_read", True, True),
    "github_issues": CapabilityClass("github_issues", "network_read", "medium", "github:issue_read", True, True),
    "github_prs": CapabilityClass("github_prs", "network_read", "medium", "github:pr_read", True, True),
    "github_issue_read": CapabilityClass("github_issue_read", "network_read", "medium", "github:issue_read", True, True),
    "github_issue_comments": CapabilityClass("github_issue_comments", "network_read", "medium", "github:issue_read", True, True),
    "github_pr_read": CapabilityClass("github_pr_read", "network_read", "medium", "github:pr_read", True, True),
    "github_pr_comments": CapabilityClass("github_pr_comments", "network_read", "medium", "github:pr_read", True, True),
    "flow_monitor": CapabilityClass("flow_monitor", "read", "medium", "runtime:flow_observe", True),
    "internet_capability": CapabilityClass("internet_capability", "read", "low", "network:status"),
    "smart_workspace": CapabilityClass("smart_workspace", "read", "low", "workspace:status"),
    "maintenance_orchestrator": CapabilityClass("maintenance_orchestrator", "read", "medium", "maintenance:status", True),
    "world_class_readiness": CapabilityClass("world_class_readiness", "read", "medium", "readiness:status", True),
    "contradiction_engine": CapabilityClass("contradiction_engine", "read", "medium", "contradiction:status", True),
    "pressure_harness": CapabilityClass("pressure_harness", "analysis", "medium", "pressure:execute", True),
    "code_workbench": CapabilityClass("code_workbench", "read", "medium", "codebase:inspect", True),
    "credential_read": CapabilityClass("credential_read", "secret_read", "critical", "credential:read", True),
    "filesystem_read": CapabilityClass("filesystem_read", "read", "high", "filesystem:read", True),
    "protected_data_read": CapabilityClass("protected_data_read", "secret_read", "critical", "protected_data:read", True),
    "protected_data_export": CapabilityClass("protected_data_export", "data_export", "critical", "protected_data:export", True, True),
    "network_export": CapabilityClass("network_export", "data_export", "critical", "data_export:network", True, True),
    "clipboard_export": CapabilityClass("clipboard_export", "data_export", "critical", "data_export:clipboard", True, True),
    "removable_export": CapabilityClass("removable_export", "data_export", "critical", "data_export:removable", True, True),
    "ipc_data_export": CapabilityClass("ipc_data_export", "data_export", "critical", "data_export:ipc", True, True),
    "cross_tenant_read": CapabilityClass("cross_tenant_read", "read", "critical", "tenant:cross_read", True),
    "tool_invoke": CapabilityClass("tool_invoke", "invoke", "high", "tool:invoke", True, True),
    "ipc_send": CapabilityClass("ipc_send", "invoke", "high", "ipc:send", True, True),
    "device_access": CapabilityClass("device_access", "device", "high", "device:access", True, True),
}


ALIASES: dict[str, str] = {
    "browser_dom_status": "browser_status",
    "github_issue_summary": "github_issues",
    "github_pr_summary": "github_prs",
    "usb_export": "removable_export",
}


def canonical_capability_kind(kind: str) -> str:
    normalized = str(kind or "").strip().lower()
    return ALIASES.get(normalized, normalized)


def capability_class(kind: str) -> CapabilityClass | None:
    canonical = canonical_capability_kind(kind)
    mutation = mutation_class(canonical)
    if mutation is not None:
        return CapabilityClass(
            name=canonical,
            mode="mutation",
            risk=mutation.risk,
            required_scope=mutation.required_scope,
            sensitive=True,
            external_side_effect=mutation.external_side_effect,
            mutation_kind=canonical,
        )
    return CAPABILITY_CLASSES.get(canonical)


def is_known_capability(kind: str) -> bool:
    return capability_class(kind) is not None
