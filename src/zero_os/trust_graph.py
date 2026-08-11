from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Iterable


NORMAL = "NORMAL"
MONITORED = "MONITORED"
RESTRICTED = "RESTRICTED"
QUARANTINED = "QUARANTINED"
REVOKED = "REVOKED"


@dataclass(frozen=True)
class TrustNode:
    principal_id: str
    identity_provenance: tuple[str, ...] = field(default_factory=tuple)
    demonstrated_scopes: frozenset[str] = field(default_factory=frozenset)
    state: str = NORMAL
    contradiction_count: int = 0
    anomaly_score: float = 0.0
    revocation_reasons: tuple[str, ...] = field(default_factory=tuple)

    def effective_scopes(self) -> frozenset[str]:
        if self.state in {QUARANTINED, REVOKED}:
            return frozenset()
        if self.state == RESTRICTED:
            return frozenset(scope for scope in self.demonstrated_scopes if scope.endswith(":status") or scope.endswith(":observe"))
        return self.demonstrated_scopes


@dataclass
class TrustGraph:
    nodes: dict[str, TrustNode] = field(default_factory=dict)

    def put(self, node: TrustNode) -> None:
        self.nodes[node.principal_id] = node

    def get(self, principal_id: str) -> TrustNode | None:
        return self.nodes.get(str(principal_id))

    def register_contradiction(self, principal_id: str, reason: str, *, severity: str = "medium") -> TrustNode:
        current = self.nodes[principal_id]
        increment = {"low": 0.1, "medium": 0.3, "high": 0.6, "critical": 1.0}.get(str(severity), 0.3)
        anomaly = min(1.0, current.anomaly_score + increment)
        contradictions = current.contradiction_count + 1
        if severity == "critical" or anomaly >= 0.9:
            state = QUARANTINED
        elif anomaly >= 0.6:
            state = RESTRICTED
        else:
            state = MONITORED
        updated = replace(
            current,
            state=state,
            contradiction_count=contradictions,
            anomaly_score=anomaly,
            revocation_reasons=current.revocation_reasons + (str(reason),),
        )
        self.nodes[principal_id] = updated
        return updated

    def revoke(self, principal_id: str, reason: str) -> TrustNode:
        current = self.nodes[principal_id]
        updated = replace(
            current,
            state=REVOKED,
            revocation_reasons=current.revocation_reasons + (str(reason),),
        )
        self.nodes[principal_id] = updated
        return updated

    def expand_scope(self, principal_id: str, scopes: Iterable[str], *, survived_stronger_pressure: bool) -> TrustNode:
        current = self.nodes[principal_id]
        if not survived_stronger_pressure:
            return current
        updated = replace(current, demonstrated_scopes=current.demonstrated_scopes.union(str(s) for s in scopes if str(s)))
        self.nodes[principal_id] = updated
        return updated
