from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict

from zero_os.capability_lease import capability_lease_context, issue_capability_lease
from zero_os.capability_registry import capability_class
from zero_os.dynamic_capability_authority import CapabilityAuthorityContext
from zero_os.pure_logic_capability_kernel import authorize_capability
from zero_os.trust_graph import TrustNode


def context_from_plan(plan_context: dict | None) -> CapabilityAuthorityContext | None:
    payload = dict((plan_context or {}).get("capability_context") or {})
    if not payload:
        return None
    return CapabilityAuthorityContext(
        principal_id=str(payload.get("principal_id", "")),
        identity_verified=bool(payload.get("identity_verified", False)),
        granted_scopes=frozenset(str(x) for x in payload.get("granted_scopes", []) if str(x)),
        contradiction_severity=str(payload.get("contradiction_severity", "none")),
        anomaly_score=float(payload.get("anomaly_score", 0.0) or 0.0),
        evidence_fresh=bool(payload.get("evidence_fresh", True)),
        tenant_id=str(payload.get("tenant_id", "")),
        resource_tenant_id=str(payload.get("resource_tenant_id", "")),
    )


def trust_from_plan(plan_context: dict | None) -> TrustNode | None:
    payload = dict((plan_context or {}).get("trust_node") or {})
    if not payload:
        return None
    return TrustNode(
        principal_id=str(payload.get("principal_id", "")),
        identity_provenance=tuple(str(x) for x in payload.get("identity_provenance", []) if str(x)),
        demonstrated_scopes=frozenset(str(x) for x in payload.get("demonstrated_scopes", []) if str(x)),
        state=str(payload.get("state", "NORMAL")),
        contradiction_count=int(payload.get("contradiction_count", 0) or 0),
        anomaly_score=float(payload.get("anomaly_score", 0.0) or 0.0),
        revocation_reasons=tuple(str(x) for x in payload.get("revocation_reasons", []) if str(x)),
    )


def gate_action(cwd: str, kind: str, *, plan_context: dict | None = None, reversible: bool = True, blast_radius: str = "local") -> dict:
    decision = authorize_capability(
        cwd,
        kind,
        context=context_from_plan(plan_context),
        trust=trust_from_plan(plan_context),
        reversible=reversible,
        blast_radius=blast_radius,
    )
    return {
        "allowed": decision.allowed,
        "kind": decision.kind,
        "reason": decision.reason,
        "disposition": decision.disposition,
        "required_scope": decision.required_scope,
        "response": asdict(decision.response),
    }


def _lease_scopes(kind: str, required_scope: str, plan_context: dict | None = None) -> set[str]:
    scopes = {str(required_scope)} if str(required_scope) else set()
    capability = capability_class(kind)
    context_payload = dict((plan_context or {}).get("capability_context") or {})
    granted = {str(x) for x in context_payload.get("granted_scopes", []) if str(x)}
    permitted_hosts = {str(x).strip().lower() for x in context_payload.get("permitted_hosts", []) if str(x).strip()}

    if capability is None:
        return scopes
    if capability.mode == "network_read":
        scopes.add("network:fetch")
    elif capability.mode == "secret_read":
        scopes.add("credential:read")
    elif capability.mode == "invoke":
        scopes.add("tool:invoke")
    elif capability.mode == "device":
        scopes.add("device:access")
    elif capability.name == "filesystem_read":
        scopes.add("filesystem:read")
    elif capability.mode == "mutation":
        if capability.external_side_effect:
            scopes.add("network:write")
        if capability.name in {"code_change", "self_repair", "recover", "store_install", "self_upgrade", "policy_change", "authority_change"}:
            scopes.add("filesystem:write")

    for host in permitted_hosts:
        scopes.add(f"host:{host}")
    for special in {"host:*", "network:local", "credential:transmit"}:
        if special in granted:
            scopes.add(special)
    return scopes


@contextmanager
def authorized_capability_context(
    cwd: str,
    kind: str,
    *,
    plan_context: dict | None = None,
    reversible: bool = True,
    blast_radius: str = "local",
    ttl_seconds: int = 30,
):
    gate = gate_action(
        cwd,
        kind,
        plan_context=plan_context,
        reversible=reversible,
        blast_radius=blast_radius,
    )
    if not gate["allowed"]:
        yield gate
        return

    context = context_from_plan(plan_context)
    principal_id = context.principal_id if context is not None else "zero-os"
    lease = issue_capability_lease(
        principal_id,
        _lease_scopes(kind, gate["required_scope"], plan_context),
        ttl_seconds=ttl_seconds,
    )
    with capability_lease_context(lease):
        payload = dict(gate)
        payload["lease"] = {
            "principal_id": lease.principal_id,
            "scopes": sorted(lease.scopes),
            "expires_at_utc": lease.expires_at_utc,
        }
        yield payload
