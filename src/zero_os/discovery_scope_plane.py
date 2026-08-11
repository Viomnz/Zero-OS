from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable


@dataclass(frozen=True)
class DiscoveryCandidate:
    candidate_id: str
    statement: str
    discovery_score: float
    requested_scope: frozenset[str] = field(default_factory=frozenset)
    alternatives: tuple[str, ...] = field(default_factory=tuple)
    assumptions: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ScopePressure:
    pressure_id: str
    scope: str
    independent: bool
    attempts_to_falsify_scope: bool
    outcome: str
    method_family: str = ""
    lineage: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ScopeDecision:
    status: str
    demonstrated_scope: frozenset[str]
    contested_scope: frozenset[str]
    independent_pressure_groups: int


def certify_scope(candidate: DiscoveryCandidate, pressures: Iterable[ScopePressure]) -> ScopeDecision:
    rows = list(pressures)
    demonstrated: set[str] = set()
    contested: set[str] = set(candidate.requested_scope)
    groups: set[tuple[str, tuple[str, ...]]] = set()

    for row in rows:
        if not row.independent or not row.attempts_to_falsify_scope:
            continue
        groups.add((row.method_family, tuple(sorted(row.lineage))))
        if row.outcome == "pass" and row.scope in candidate.requested_scope:
            demonstrated.add(row.scope)
            contested.discard(row.scope)
        elif row.outcome in {"fail", "unknown", "inconclusive"}:
            contested.add(row.scope)
            demonstrated.discard(row.scope)

    status = "SURVIVED_IN_SCOPE" if demonstrated and not contested else "CONTESTED" if contested else "UNTESTED"
    return ScopeDecision(status, frozenset(demonstrated), frozenset(contested), len(groups))


def select_discovery_winner(candidates: Iterable[DiscoveryCandidate]) -> DiscoveryCandidate | None:
    rows = list(candidates)
    if not rows:
        return None
    return max(rows, key=lambda item: float(item.discovery_score))


def authority_from_discovery_forbidden(candidate: DiscoveryCandidate, scope: ScopeDecision) -> bool:
    """Always false: discovery fit cannot itself grant scope authority."""
    _ = candidate
    _ = scope
    return False
