from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable


AUTHORITY_PROVISIONAL = "provisional"
AUTHORITY_CONTESTED = "contested"
AUTHORITY_REJECTED = "rejected"


@dataclass(frozen=True)
class Evidence:
    source: str
    supports: bool
    independent_group: str
    quality: float = 1.0
    scope: frozenset[str] = field(default_factory=frozenset)


@dataclass(frozen=True)
class AuthorityDecision:
    status: str
    authority: float
    demonstrated_scope: frozenset[str]
    reasons: tuple[str, ...]

    @property
    def permits_authority(self) -> bool:
        return self.status == AUTHORITY_PROVISIONAL and self.authority > 0.0


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def certify_scope(
    claim_scope: Iterable[str],
    evidence: Iterable[Evidence],
    *,
    proposer_source: str = "",
    minimum_independent_groups: int = 2,
) -> AuthorityDecision:
    """Certify only authority demonstrated independently of the proposer.

    Pure Logic invariant: proposing, scoring, winning, or internally verifying a
    claim never certifies the scope of that claim. Authority is provisional,
    scoped, revocable, and must be supported by independent evidence groups.
    """
    requested = frozenset(str(item).strip() for item in claim_scope if str(item).strip())
    records = tuple(evidence)
    reasons: list[str] = []

    if not requested:
        return AuthorityDecision(AUTHORITY_REJECTED, 0.0, frozenset(), ("scope_missing",))

    independent = tuple(
        item
        for item in records
        if item.source != proposer_source and item.independent_group and _clamp01(item.quality) > 0.0
    )
    if not independent:
        return AuthorityDecision(AUTHORITY_CONTESTED, 0.0, frozenset(), ("independent_evidence_missing",))

    opposing = tuple(item for item in independent if not item.supports)
    if opposing:
        reasons.append("independent_contradiction_present")

    supporting = tuple(item for item in independent if item.supports)
    groups = {item.independent_group for item in supporting}
    if len(groups) < max(1, int(minimum_independent_groups)):
        reasons.append("insufficient_independent_groups")

    demonstrated = set(requested)
    for dimension in requested:
        dimension_support = [item for item in supporting if dimension in item.scope]
        dimension_groups = {item.independent_group for item in dimension_support}
        if len(dimension_groups) < max(1, int(minimum_independent_groups)):
            demonstrated.discard(dimension)

    if demonstrated != set(requested):
        reasons.append("scope_not_fully_demonstrated")

    if reasons:
        return AuthorityDecision(AUTHORITY_CONTESTED, 0.0, frozenset(demonstrated), tuple(reasons))

    quality_by_group: dict[str, float] = {}
    for item in supporting:
        if requested.issubset(item.scope):
            quality_by_group[item.independent_group] = max(
                quality_by_group.get(item.independent_group, 0.0), _clamp01(item.quality)
            )
    authority = min(quality_by_group.values()) if quality_by_group else 0.0
    if authority <= 0.0:
        return AuthorityDecision(AUTHORITY_CONTESTED, 0.0, frozenset(), ("evidence_quality_zero",))

    return AuthorityDecision(
        AUTHORITY_PROVISIONAL,
        authority,
        requested,
        ("independent_scope_certified", "authority_is_provisional_and_revocable"),
    )


def certify_candidate(candidate: dict[str, Any], evidence: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Dictionary boundary for existing Zero-OS modules."""
    records = [
        Evidence(
            source=str(item.get("source", "")),
            supports=bool(item.get("supports", False)),
            independent_group=str(item.get("independent_group", "")),
            quality=float(item.get("quality", 0.0) or 0.0),
            scope=frozenset(str(x) for x in item.get("scope", []) if str(x)),
        )
        for item in evidence
    ]
    decision = certify_scope(
        candidate.get("scope", []),
        records,
        proposer_source=str(candidate.get("source", "")),
    )
    return {
        "status": decision.status,
        "authority": decision.authority,
        "demonstrated_scope": sorted(decision.demonstrated_scope),
        "reasons": list(decision.reasons),
        "discovery_confidence_ignored_for_scope": True,
    }
