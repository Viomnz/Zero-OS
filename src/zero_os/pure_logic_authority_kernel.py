from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from zero_os.authority_ledger import AuthorityLedger
from zero_os.objective_authority import ObjectiveAuthorityLedger
from zero_os.pure_logic_control_loop import (
    CandidateAction,
    ControlHistoryEntry,
    ControllerAuthorityState,
    ControllerContract,
    StateEstimate,
    authorize_control_step,
)
from zero_os.resource_law_budget import VerificationBudget


_AUTONOMOUS_CAPABILITIES = frozenset({
    "self_repair",
    "self_upgrade",
    "run_runtime",
    "autonomous_action",
    "autonomous_rollout",
    "goal_progress",
})


@dataclass(frozen=True)
class IdentityAuthority:
    principal_id: str
    provenance: tuple[str, ...]
    authenticated: bool
    demonstrated_scopes: frozenset[str] = field(default_factory=frozenset)
    trust_state: str = "NORMAL"


@dataclass(frozen=True)
class ControllerEvidence:
    """Raw controller evidence that constitutional authority must recompute.

    This is intentionally not a boolean certificate. The final authority layer
    reruns the common control-loop contract from the underlying contract,
    observation, candidate action, history and revocation state.
    """

    contract: ControllerContract
    controller_authority: ControllerAuthorityState
    estimate: StateEstimate
    action: CandidateAction
    history: tuple[ControlHistoryEntry, ...] = field(default_factory=tuple)
    active_revocation_conditions: tuple[str, ...] = field(default_factory=tuple)


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
    controller_evidence: ControllerEvidence | None = None


@dataclass(frozen=True)
class ConstitutionalDecision:
    allowed: bool
    status: str
    reasons: tuple[str, ...]
    verification_depth: int
    required_evidence_groups: int
    controller_evidence_recomputed: bool = False
    controller_reason: str = ""


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
    controller_recomputed = False
    controller_reason = ""

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
    objective_authorized = objective_ledger.authorize(request.objective_id, request.action_scope, active_dependency_ids)
    if not objective_authorized:
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

    # Autonomous capability cannot self-assert controller eligibility. The
    # constitutional layer recomputes the control-loop decision from raw
    # evidence every time authority is requested.
    if request.requested_capability in _AUTONOMOUS_CAPABILITIES:
        evidence = request.controller_evidence
        if evidence is None:
            reasons.append("autonomous_controller_evidence_missing")
        else:
            controller_recomputed = True
            loop_decision = authorize_control_step(
                contract=evidence.contract,
                controller_authority=evidence.controller_authority,
                objective_authorized=objective_authorized,
                estimate=evidence.estimate,
                action=evidence.action,
                history=evidence.history,
                active_revocation_conditions=evidence.active_revocation_conditions,
            )
            controller_reason = loop_decision.reason
            if evidence.contract.objective_id != request.objective_id:
                reasons.append("controller_objective_binding_mismatch")
            if evidence.contract.authority_id != request.authority_id:
                reasons.append("controller_authority_binding_mismatch")
            if evidence.action.capability_scope != request.action_scope:
                reasons.append("controller_scope_binding_mismatch")
            if evidence.action.action_id != request.requested_capability:
                reasons.append("controller_action_binding_mismatch")
            if not loop_decision.allowed:
                reasons.append(f"controller_not_eligible:{loop_decision.reason}")
            if loop_decision.permitted_capability_scope != request.action_scope:
                reasons.append("controller_permitted_scope_mismatch")

    return ConstitutionalDecision(
        allowed=not reasons,
        status="PROVISIONAL_SCOPED_AUTHORITY" if not reasons else "DENY_OR_INVESTIGATE",
        reasons=tuple(reasons),
        verification_depth=budget.depth,
        required_evidence_groups=budget.required_evidence_groups,
        controller_evidence_recomputed=controller_recomputed,
        controller_reason=controller_reason,
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
        "unknown_remains_unknown_until_discriminating_evidence_exists",
        "autonomous_controller_eligibility_is_recomputed_not_self_asserted",
        "control_loop_never_grants_final_execution_authority",
    )
