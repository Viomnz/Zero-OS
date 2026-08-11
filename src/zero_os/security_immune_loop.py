from __future__ import annotations

from dataclasses import dataclass

from zero_os.adaptive_defense_response import DefenseResponse, choose_defense_response
from zero_os.trust_graph import TrustGraph, TrustNode


@dataclass(frozen=True)
class SecurityObservation:
    principal_id: str
    event_id: str
    contradiction: bool
    severity: str
    reason: str
    reversible: bool = True
    blast_radius: str = "local"


@dataclass(frozen=True)
class SecurityImmuneResult:
    principal: TrustNode
    response: DefenseResponse
    preserve_failure: bool
    investigate_root_cause: bool
    search_pattern_elsewhere: bool
    require_stronger_retest: bool


def apply_security_observation(graph: TrustGraph, observation: SecurityObservation) -> SecurityImmuneResult:
    principal = graph.get(observation.principal_id)
    if principal is None:
        principal = TrustNode(principal_id=observation.principal_id)
        graph.put(principal)

    if observation.contradiction:
        principal = graph.register_contradiction(
            observation.principal_id,
            f"{observation.event_id}:{observation.reason}",
            severity=observation.severity,
        )
        disposition = "quarantine" if principal.state in {"QUARANTINED", "REVOKED"} else "restrict"
        response = choose_defense_response(
            disposition=disposition,
            reversible=observation.reversible,
            blast_radius=observation.blast_radius,
        )
        return SecurityImmuneResult(principal, response, True, True, True, True)

    disposition = "monitor" if principal.state == "MONITORED" else "allow"
    response = choose_defense_response(
        disposition=disposition,
        reversible=observation.reversible,
        blast_radius=observation.blast_radius,
    )
    return SecurityImmuneResult(principal, response, False, False, False, False)
