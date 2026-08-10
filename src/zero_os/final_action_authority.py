from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable

from zero_os.authority_ledger import AuthorityLedger
from zero_os.evidence_binding import EvidenceRecord, evidence_for_exact_claim, independent_support_count


@dataclass(frozen=True)
class ActionAuthorityRequest:
    action_id: str
    subject_id: str
    claim_type: str
    claim_value: Any
    state_revision: str
    required_scope: str
    authority_id: str
    mutating: bool = True


@dataclass(frozen=True)
class ActionAuthorityDecision:
    allowed: bool
    reason: str
    authority_id: str
    required_scope: str
    independent_support_groups: int


def authorize_action(
    request: ActionAuthorityRequest,
    *,
    ledger: AuthorityLedger,
    evidence: Iterable[EvidenceRecord],
    active_revocation_conditions: Iterable[str] = (),
    now_utc: datetime | None = None,
    minimum_independent_groups: int = 2,
) -> ActionAuthorityDecision:
    """Final authority boundary immediately before a state-changing action.

    The action is denied unless exact-claim evidence, dependency health, freshness,
    scope, and revocation checks all survive. Discovery confidence is intentionally
    absent from this API.
    """
    if not request.mutating:
        return ActionAuthorityDecision(True, "read_only", request.authority_id, request.required_scope, 0)

    ledger.revoke_for_condition(active_revocation_conditions)
    record = ledger.get(request.authority_id)
    if record is None:
        return ActionAuthorityDecision(False, "authority_record_missing", request.authority_id, request.required_scope, 0)

    exact = evidence_for_exact_claim(
        evidence,
        subject_id=request.subject_id,
        claim_type=request.claim_type,
        value=request.claim_value,
        state_revision=request.state_revision,
    )
    support_groups = independent_support_count(exact, request.required_scope)
    if support_groups < max(1, int(minimum_independent_groups)):
        return ActionAuthorityDecision(False, "independent_exact_claim_evidence_missing", request.authority_id, request.required_scope, support_groups)

    if any(not item.supports and request.required_scope in item.scope for item in exact):
        return ActionAuthorityDecision(False, "contradictory_exact_claim_evidence", request.authority_id, request.required_scope, support_groups)

    expected_fingerprint = record.value_fingerprint
    from zero_os.evidence_binding import canonical_fingerprint

    if canonical_fingerprint(request.claim_value) != expected_fingerprint:
        return ActionAuthorityDecision(False, "claim_value_changed", request.authority_id, request.required_scope, support_groups)
    if record.subject_id != request.subject_id or record.claim_type != request.claim_type:
        return ActionAuthorityDecision(False, "authority_subject_mismatch", request.authority_id, request.required_scope, support_groups)
    if record.state_revision != request.state_revision:
        return ActionAuthorityDecision(False, "state_revision_changed", request.authority_id, request.required_scope, support_groups)

    if not ledger.authorize(request.authority_id, request.required_scope, now_utc=now_utc or datetime.now(timezone.utc)):
        return ActionAuthorityDecision(False, "authority_not_active_for_scope", request.authority_id, request.required_scope, support_groups)

    return ActionAuthorityDecision(True, "provisional_scoped_authority", request.authority_id, request.required_scope, support_groups)
