from __future__ import annotations

from dataclasses import asdict

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
