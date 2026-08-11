from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from zero_os.authority_ledger import AuthorityLedger
from zero_os.objective_authority import ObjectiveAuthorityLedger
from zero_os.resource_law_budget import VerificationBudget


@dataclass(frozen=True)
class IdentityAuthority:
    principal_id: str
    provenance: tuple[str, ...]
    authenticated: bool
    demonstrated_scopes: frozenset[str] = field(default_factory=frozenset)
    trust_state: str = "NORMAL"


@dataclass(frozen=True)
class ConstitutionalRequest:
    actor: IdentityAuthority
    action_scope: str
    objective_id: str
    authority_id: str
    requested_capability: str
    consequence: str
    reversible: bool
    contradictions: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ConstitutionalDecision:
    allowed: bool
    status: str
    reasons: tuple[str, ...]
    verification_depth: int
    required_evidence_groups: int


def decide(
    *,
    request: ConstitutionalRequest,
    authority_ledger: AuthorityLedger,
    objective_ledger: ObjectiveAuthorityLedger,
    budget: VerificationBudget,
    active_dependency_ids: Iterable[str],
    correction_plane_allows: bool = True,
    legal_state_ok: bool = True,
) -> ConstitutionalDecision:
    reasons: list[str] = []

    if not request.actor.provenance:
        reasons.append("identity_provenance_missing")
    if request.actor.trust_state in {"QUARANTINED", "REVOKED"}:
        reasons.append("principal_trust_contested_or_revoked")
    if request.action_scope not in request.actor.demonstrated_scopes:
        reasons.append("identity_scope_not_demonstrated")
    if request.contradictions:
        reasons.append("active_contradiction_present")
    if not authority_ledger.authorize(request.authority_id, request.action_scope):
        reasons.append("claim_authority_missing_or_out_of_scope")
    if not objective_ledger.authorize(request.objective_id, request.action_scope, active_dependency_ids):
        reasons.append("objective_authority_missing_or_out_of_scope")
    if not correction_plane_allows:
        reasons.append("protected_correction_plane_denied")
    if not legal_state_ok:
        reasons.append("legal_state_invariant_failed")
    if budget.require_reversible_path and not request.reversible:
        reasons.append("required_reversible_path_missing")

    # Authentication is consequence-sensitive rather than a global boolean.
    if request.consequence in {"high", "critical"} and not request.actor.authenticated:
        reasons.append("strong_identity_evidence_required")

    return ConstitutionalDecision(
        allowed=not reasons,
        status="PROVISIONAL_SCOPED_AUTHORITY" if not reasons else "DENY_OR_INVESTIGATE",
        reasons=tuple(reasons),
        verification_depth=budget.depth,
        required_evidence_groups=budget.required_evidence_groups,
    )


def constitutional_invariants() -> tuple[str, ...]:
    return (
        "discovery_confidence_never_grants_scope_authority",
        "memory_never_counts_as_independent_evidence_by_itself",
        "no_component_certifies_its_own_authority",
        "protected_core_is_runtime_tamper_resistant_but_revision_capable",
        "privileged_identity_requires_provenance_and_scoped_authority",
        "objectives_have_separate_revocable_authority",
        "critical_actions_require_legal_state_checks",
        "critical_actions_require_independent_outcome_verification",
        "authority_expiry_and_revocation_are_enforced",
        "unknown_remains_unknown_until discriminating evidence exists",
    )
