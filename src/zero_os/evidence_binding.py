from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Iterable


def canonical_fingerprint(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class EvidenceRecord:
    evidence_id: str
    subject_id: str
    claim_type: str
    value_fingerprint: str
    state_revision: str
    source: str
    source_lineage: frozenset[str]
    method_family: str
    supports: bool
    scope: frozenset[str]
    quality: float = 1.0
    test_id: str = ""

    def binds_to(
        self,
        *,
        subject_id: str,
        claim_type: str,
        value_fingerprint: str,
        state_revision: str,
    ) -> bool:
        return bool(
            self.subject_id == str(subject_id)
            and self.claim_type == str(claim_type)
            and self.value_fingerprint == str(value_fingerprint)
            and self.state_revision == str(state_revision)
        )


def verified_independence_groups(records: Iterable[EvidenceRecord]) -> list[list[EvidenceRecord]]:
    """Group evidence by actual shared lineage/method overlap, not caller labels.

    Two records are treated as dependent if their source lineages overlap or their
    method family is identical. This is deliberately conservative: independence is
    something to demonstrate, not something a caller gets by inventing two names.
    """
    groups: list[list[EvidenceRecord]] = []
    for record in records:
        placed = False
        for group in groups:
            if any(
                bool(record.source_lineage.intersection(other.source_lineage))
                or (record.method_family and record.method_family == other.method_family)
                for other in group
            ):
                group.append(record)
                placed = True
                break
        if not placed:
            groups.append([record])
    return groups


def evidence_for_exact_claim(
    records: Iterable[EvidenceRecord],
    *,
    subject_id: str,
    claim_type: str,
    value: Any,
    state_revision: str,
) -> tuple[EvidenceRecord, ...]:
    fingerprint = canonical_fingerprint(value)
    return tuple(
        record
        for record in records
        if record.binds_to(
            subject_id=subject_id,
            claim_type=claim_type,
            value_fingerprint=fingerprint,
            state_revision=state_revision,
        )
    )


def independent_support_count(records: Iterable[EvidenceRecord], scope: str) -> int:
    supporting = [record for record in records if record.supports and str(scope) in record.scope]
    return len(verified_independence_groups(supporting))
