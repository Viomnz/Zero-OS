from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable

from zero_os.authority_integrity_audit import audit_authority_integrity
from zero_os.authority_ledger import AuthorityLedger
from zero_os.evidence_binding import EvidenceRecord, evidence_for_exact_claim, independent_support_count
from zero_os.execution_authority_ticket import issue_execution_ticket
from zero_os.mutation_registry import canonical_mutation_kind, mutation_class
from zero_os.objective_authority import ObjectiveAuthorityLedger
from zero_os.pure_logic_authority_kernel import ConstitutionalRequest, decide as constitutional_decide
from zero_os.resource_law_budget import VerificationBudget


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
    """Exact claim authority immediately before a state-changing action.

    This layer proves only claim/evidence authority. It cannot mint runtime
    authority by itself. Mutation tickets additionally require the v5
    constitutional authority kernel.
    """
    if not request.mutating:
        return ActionAuthorityDecision(True, "read_only", request.authority_id, request.required_scope, 0)

    integrity = audit_authority_integrity(ledger)
    if not bool(integrity.get("authority_integrity_permitted", False)):
        return ActionAuthorityDecision(False, "authority_graph_integrity_failed", request.authority_id, request.required_scope, 0)

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

    from zero_os.evidence_binding import canonical_fingerprint

    if canonical_fingerprint(request.claim_value) != record.value_fingerprint:
        return ActionAuthorityDecision(False, "claim_value_changed", request.authority_id, request.required_scope, support_groups)
    if record.subject_id != request.subject_id or record.claim_type != request.claim_type:
        return ActionAuthorityDecision(False, "authority_subject_mismatch", request.authority_id, request.required_scope, support_groups)
    if record.state_revision != request.state_revision:
        return ActionAuthorityDecision(False, "state_revision_changed", request.authority_id, request.required_scope, support_groups)

    if not ledger.authorize(request.authority_id, request.required_scope, now_utc=now_utc or datetime.now(timezone.utc)):
        return ActionAuthorityDecision(False, "authority_not_active_for_scope", request.authority_id, request.required_scope, support_groups)

    return ActionAuthorityDecision(True, "provisional_scoped_authority", request.authority_id, request.required_scope, support_groups)


def authorize_and_issue_execution_ticket(
    cwd: str,
    action_kind: str,
    request: ActionAuthorityRequest,
    *,
    ledger: AuthorityLedger,
    evidence: Iterable[EvidenceRecord],
    constitutional_request: ConstitutionalRequest | None = None,
    objective_ledger: ObjectiveAuthorityLedger | None = None,
    verification_budget: VerificationBudget | None = None,
    active_dependency_ids: Iterable[str] = (),
    correction_plane_allows: bool = True,
    legal_state_ok: bool = True,
    active_revocation_conditions: Iterable[str] = (),
    now_utc: datetime | None = None,
    minimum_independent_groups: int = 2,
    ttl_seconds: int = 30,
) -> dict[str, Any]:
    """Mint a ticket only when exact claim authority AND v5 constitution survive.

    This is the causal integration point between the old mutation runtime and the
    v5 Pure Logic Authority Kernel. Missing constitutional context fails closed.
    Discovery confidence, planner scores, memory weights, and self-reported
    success are intentionally not accepted here.
    """
    canonical_kind = canonical_mutation_kind(action_kind)
    spec = mutation_class(canonical_kind)
    if request.mutating and spec is None:
        return {"ok": False, "reason": "unknown_mutation_kind", "decision": None, "constitutional_decision": None, "ticket": None}
    if request.mutating and request.required_scope != spec.required_scope:
        return {
            "ok": False,
            "reason": "registered_mutation_scope_mismatch",
            "required_scope": spec.required_scope,
            "requested_scope": request.required_scope,
            "decision": None,
            "constitutional_decision": None,
            "ticket": None,
        }

    if request.mutating and (constitutional_request is None or objective_ledger is None or verification_budget is None):
        return {
            "ok": False,
            "reason": "constitutional_context_missing",
            "decision": None,
            "constitutional_decision": None,
            "ticket": None,
        }

    constitutional = None
    if request.mutating:
        assert constitutional_request is not None
        assert objective_ledger is not None
        assert verification_budget is not None
        if constitutional_request.action_scope != request.required_scope:
            return {
                "ok": False,
                "reason": "constitutional_scope_mismatch",
                "required_scope": request.required_scope,
                "constitutional_scope": constitutional_request.action_scope,
                "decision": None,
                "constitutional_decision": None,
                "ticket": None,
            }
        if constitutional_request.authority_id != request.authority_id:
            return {
                "ok": False,
                "reason": "constitutional_authority_mismatch",
                "decision": None,
                "constitutional_decision": None,
                "ticket": None,
            }
        if constitutional_request.requested_capability != canonical_kind:
            return {
                "ok": False,
                "reason": "constitutional_capability_mismatch",
                "expected_capability": canonical_kind,
                "constitutional_capability": constitutional_request.requested_capability,
                "decision": None,
                "constitutional_decision": None,
                "ticket": None,
            }

        constitutional = constitutional_decide(
            request=constitutional_request,
            authority_ledger=ledger,
            objective_ledger=objective_ledger,
            budget=verification_budget,
            active_dependency_ids=active_dependency_ids,
            correction_plane_allows=correction_plane_allows,
            legal_state_ok=legal_state_ok,
        )
        if not constitutional.allowed:
            return {
                "ok": False,
                "reason": "constitutional_authority_denied",
                "decision": None,
                "constitutional_decision": constitutional,
                "ticket": None,
            }
        if constitutional.required_evidence_groups > max(1, int(minimum_independent_groups)):
            minimum_independent_groups = constitutional.required_evidence_groups

    decision = authorize_action(
        request,
        ledger=ledger,
        evidence=evidence,
        active_revocation_conditions=active_revocation_conditions,
        now_utc=now_utc,
        minimum_independent_groups=minimum_independent_groups,
    )
    if not decision.allowed:
        return {"ok": False, "decision": decision, "constitutional_decision": constitutional, "ticket": None}
    if not request.mutating:
        return {"ok": True, "decision": decision, "constitutional_decision": constitutional, "ticket": None}

    ticket = issue_execution_ticket(
        cwd,
        action_kind=canonical_kind,
        authority_id=request.authority_id,
        subject_id=request.subject_id,
        required_scope=spec.required_scope,
        state_revision=request.state_revision,
        ttl_seconds=ttl_seconds,
    )
    return {"ok": True, "decision": decision, "constitutional_decision": constitutional, "ticket": ticket}


def authorize_action_and_mint_ticket(*args, **kwargs):
    """Compatibility name; semantics are v5 constitutional and fail closed."""
    return authorize_and_issue_execution_ticket(*args, **kwargs)
