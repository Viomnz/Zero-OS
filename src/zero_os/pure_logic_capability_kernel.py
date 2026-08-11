from __future__ import annotations

from dataclasses import dataclass

from zero_os.adaptive_defense_response import DefenseResponse, choose_defense_response
from zero_os.capability_registry import capability_class
from zero_os.dynamic_capability_authority import CapabilityAuthorityContext, CapabilityAuthorityDecision, evaluate_capability_authority
from zero_os.pure_logic_runtime_kernel import authorize_runtime_mutation
from zero_os.trust_graph import TrustNode


@dataclass(frozen=True)
class CapabilityKernelDecision:
    allowed: bool
    kind: str
    reason: str
    disposition: str
    required_scope: str
    response: DefenseResponse


def authorize_capability(
    cwd: str,
    kind: str,
    *,
    context: CapabilityAuthorityContext | None = None,
    trust: TrustNode | None = None,
    reversible: bool = True,
    blast_radius: str = "local",
) -> CapabilityKernelDecision:
    capability = capability_class(kind)
    if capability is None:
        response = choose_defense_response(disposition="deny", reversible=reversible, blast_radius=blast_radius)
        return CapabilityKernelDecision(False, str(kind), "unknown_capability", "deny", "", response)

    # Mutation tickets are consumed by the existing mutation boundary. This kernel
    # refuses to duplicate-consume them; it only declares the capability class here.
    if capability.mode == "mutation":
        mutation = authorize_runtime_mutation(cwd, kind, consume=False)
        disposition = "allow" if mutation.allowed else "deny"
        response = choose_defense_response(disposition=disposition, reversible=reversible, blast_radius=blast_radius)
        return CapabilityKernelDecision(mutation.allowed, capability.name, mutation.reason, disposition, capability.required_scope, response)

    if not capability.sensitive and capability.risk == "low":
        response = choose_defense_response(disposition="allow", reversible=reversible, blast_radius=blast_radius)
        return CapabilityKernelDecision(True, capability.name, "low_risk_read", "allow", capability.required_scope, response)

    if context is None:
        response = choose_defense_response(disposition="restrict", reversible=reversible, blast_radius=blast_radius)
        return CapabilityKernelDecision(False, capability.name, "capability_context_missing", "restrict", capability.required_scope, response)

    decision: CapabilityAuthorityDecision = evaluate_capability_authority(capability, context, trust)
    response = choose_defense_response(disposition=decision.disposition, reversible=reversible, blast_radius=blast_radius)
    return CapabilityKernelDecision(
        decision.allowed,
        capability.name,
        decision.reason,
        decision.disposition,
        capability.required_scope,
        response,
    )
