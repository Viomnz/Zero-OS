from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable


@dataclass(frozen=True)
class OutcomeEvidence:
    source_id: str
    method_family: str
    observed_state: str
    supports_expected: bool
    lineage: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class OutcomeDecision:
    verified: bool
    status: str
    independent_groups: int
    contradictions: tuple[str, ...]


def _independent_group_key(item: OutcomeEvidence) -> tuple[str, tuple[str, ...]]:
    return (str(item.method_family), tuple(sorted(str(x) for x in item.lineage)))


def verify_outcome(
    *,
    actor_id: str,
    expected_state: str,
    evidence: Iterable[OutcomeEvidence],
    required_independent_groups: int = 1,
) -> OutcomeDecision:
    rows = list(evidence)
    contradictions = tuple(
        f"{row.source_id}:{row.observed_state}" for row in rows if not row.supports_expected
    )
    supporting = [row for row in rows if row.supports_expected and row.source_id != actor_id]
    groups = {_independent_group_key(row) for row in supporting}
    verified = not contradictions and len(groups) >= max(1, int(required_independent_groups))
    return OutcomeDecision(
        verified=verified,
        status="VERIFIED_IN_SCOPE" if verified else "CONTESTED",
        independent_groups=len(groups),
        contradictions=contradictions,
    )
