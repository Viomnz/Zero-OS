from __future__ import annotations

from dataclasses import dataclass, field
from math import isfinite
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
    if type(value) not in (int, float) or not isfinite(value):
        return 0.0
    return max(0.0, min(1.0, value))


def _scope(value: Any) -> frozenset[str]:
    if isinstance(value, (str, bytes, dict)):
        raise ValueError("scope must be a collection of nonempty strings")
    items = tuple(value)
    if any(not isinstance(item, str) or not item.strip() for item in items):
        raise ValueError("invalid scope dimension")
    return frozenset(item.strip() for item in items)


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
    try:
        requested = _scope(claim_scope)
        records = tuple(evidence)
        if not isinstance(proposer_source, str):
            raise ValueError("invalid proposer")
        if type(minimum_independent_groups) is not int or minimum_independent_groups < 1:
            raise ValueError("invalid independent group threshold")
    except (TypeError, ValueError):
        return AuthorityDecision(AUTHORITY_REJECTED, 0.0, frozenset(), ("malformed_authority_request",))
    reasons: list[str] = []

    if not requested:
        return AuthorityDecision(AUTHORITY_REJECTED, 0.0, frozenset(), ("scope_missing",))

    # A malformed contradiction must not disappear during coercion/filtering.
    try:
        for item in records:
            if (not isinstance(item, Evidence)
                or not isinstance(item.source, str) or not item.source.strip()
                or not isinstance(item.independent_group, str) or not item.independent_group.strip()
                or type(item.supports) is not bool
                or type(item.quality) not in (int, float)
                or not 0.0 <= item.quality <= 1.0 or not isfinite(item.quality)
                or not _scope(item.scope)):
                raise ValueError("malformed evidence")
    except (TypeError, ValueError):
        return AuthorityDecision(AUTHORITY_CONTESTED, 0.0, frozenset(), ("malformed_evidence",))

    # Changing a label cannot give a single source independent failure modes.
    source_groups: dict[str, set[str]] = {}
    for item in records:
        source_groups.setdefault(item.source.strip(), set()).add(item.independent_group.strip())
    if any(len(groups) > 1 for groups in source_groups.values()):
        return AuthorityDecision(AUTHORITY_CONTESTED, 0.0, frozenset(), ("source_lineage_conflict",))

    proposer_groups = {item.independent_group.strip() for item in records
                       if item.source.strip() == proposer_source.strip()}

    independent = tuple(
        item
        for item in records
        if item.source.strip() != proposer_source.strip()
        and item.independent_group.strip() not in proposer_groups
        and _clamp01(item.quality) > 0.0
    )
    if not independent:
        return AuthorityDecision(AUTHORITY_CONTESTED, 0.0, frozenset(), ("independent_evidence_missing",))

    opposing = tuple(item for item in records if not item.supports
                     and item.quality > 0.0 and requested.intersection(_scope(item.scope)))
    if opposing:
        reasons.append("independent_contradiction_present" if any(item in independent for item in opposing)
                       else "contradiction_present")

    supporting = tuple(item for item in independent if item.supports)
    groups = {item.independent_group.strip() for item in supporting}
    if len(groups) < max(1, int(minimum_independent_groups)):
        reasons.append("insufficient_independent_groups")

    demonstrated = set(requested)
    for dimension in requested:
        dimension_support = [item for item in supporting if dimension in _scope(item.scope)]
        dimension_groups = {item.independent_group.strip() for item in dimension_support}
        if len(dimension_groups) < max(1, int(minimum_independent_groups)):
            demonstrated.discard(dimension)

    if demonstrated != set(requested):
        reasons.append("scope_not_fully_demonstrated")

    if reasons:
        return AuthorityDecision(AUTHORITY_CONTESTED, 0.0, frozenset(demonstrated), tuple(reasons))

    # Every dimension needs its own independent support. Do not require each
    # individual record to cover the entire union of otherwise verified scopes.
    dimension_quality = []
    for dimension in requested:
        quality_by_group: dict[str, float] = {}
        for item in supporting:
            if dimension in _scope(item.scope):
                group = item.independent_group.strip()
                quality_by_group[group] = max(quality_by_group.get(group, 0.0), item.quality)
        dimension_quality.append(min(quality_by_group.values()))
    authority = min(dimension_quality)
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
    try:
        records = [
            Evidence(
                source=item.get("source", ""),
                supports=item.get("supports"),
                independent_group=item.get("independent_group", ""),
                quality=item.get("quality", 0.0),
                scope=_scope(item.get("scope", [])),
            )
            for item in evidence
        ]
        decision = certify_scope(
            candidate.get("scope", []), records,
            proposer_source=candidate.get("source", ""),
        )
    except (AttributeError, TypeError, ValueError):
        decision = AuthorityDecision(AUTHORITY_CONTESTED, 0.0, frozenset(), ("malformed_evidence",))
    return {
        "status": decision.status,
        "authority": decision.authority,
        "demonstrated_scope": sorted(decision.demonstrated_scope),
        "reasons": list(decision.reasons),
        "discovery_confidence_ignored_for_scope": True,
    }
