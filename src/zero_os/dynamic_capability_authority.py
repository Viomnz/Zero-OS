from __future__ import annotations

from dataclasses import dataclass

from zero_os.capability_registry import CapabilityClass
from zero_os.trust_graph import MONITORED, NORMAL, QUARANTINED, RESTRICTED, REVOKED, TrustNode


@dataclass(frozen=True)
class CapabilityAuthorityContext:
    principal_id: str
    identity_verified: bool
    granted_scopes: frozenset[str]
    contradiction_severity: str = "none"
    anomaly_score: float = 0.0
    evidence_fresh: bool = True
    tenant_id: str = ""
    resource_tenant_id: str = ""


@dataclass(frozen=True)
class CapabilityAuthorityDecision:
    allowed: bool
    disposition: str
    reason: str
    required_scope: str
    effective_scopes: frozenset[str]


def evaluate_capability_authority(
    capability: CapabilityClass,
    context: CapabilityAuthorityContext,
    trust: TrustNode | None = None,
) -> CapabilityAuthorityDecision:
    if not context.identity_verified and capability.sensitive:
        return CapabilityAuthorityDecision(False, "restrict", "identity_not_verified", capability.required_scope, frozenset())
    if not context.evidence_fresh and capability.risk in {"high", "critical"}:
        return CapabilityAuthorityDecision(False, "restrict", "stale_authority_evidence", capability.required_scope, frozenset())
    if context.tenant_id and context.resource_tenant_id and context.tenant_id != context.resource_tenant_id:
        if capability.required_scope != "tenant:cross_read":
            return CapabilityAuthorityDecision(False, "quarantine", "cross_tenant_scope_not_explicit", capability.required_scope, frozenset())

    effective = set(context.granted_scopes)
    state = NORMAL
    anomaly = max(0.0, min(1.0, float(context.anomaly_score)))
    if trust is not None:
        effective.intersection_update(trust.effective_scopes())
        state = trust.state
        anomaly = max(anomaly, trust.anomaly_score)

    if state in {REVOKED, QUARANTINED}:
        return CapabilityAuthorityDecision(False, "quarantine", "principal_authority_unavailable", capability.required_scope, frozenset(effective))
    if context.contradiction_severity == "critical" or anomaly >= 0.9:
        return CapabilityAuthorityDecision(False, "quarantine", "critical_runtime_contradiction", capability.required_scope, frozenset(effective))
    if state == RESTRICTED or context.contradiction_severity == "high" or anomaly >= 0.6:
        if capability.risk != "low":
            return CapabilityAuthorityDecision(False, "restrict", "authority_reduced_by_runtime_evidence", capability.required_scope, frozenset(effective))
    if capability.required_scope not in effective:
        return CapabilityAuthorityDecision(False, "deny", "scope_not_demonstrated", capability.required_scope, frozenset(effective))
    disposition = "monitor" if state == MONITORED or anomaly >= 0.25 else "allow"
    return CapabilityAuthorityDecision(True, disposition, "scoped_capability_authority", capability.required_scope, frozenset(effective))
