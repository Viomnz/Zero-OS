from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable


class CausalState(str, Enum):
    UNTESTED = "UNTESTED"
    OBSERVATIONAL_ONLY = "OBSERVATIONAL_ONLY"
    PROVISIONAL = "PROVISIONAL"
    SURVIVED_INTERVENTION = "SURVIVED_INTERVENTION"
    CONTESTED = "CONTESTED"
    REVOKED = "REVOKED"


@dataclass(frozen=True)
class CausalEvidence:
    evidence_id: str
    source: str
    method_family: str
    lineage: str
    observational: bool = True
    intervention: bool = False
    counterfactual: bool = False
    confounders_addressed: tuple[str, ...] = field(default_factory=tuple)
    contradicted: bool = False


@dataclass(frozen=True)
class CausalClaim:
    claim_id: str
    cause_subject: str
    effect_subject: str
    requested_scope: tuple[str, ...]
    demonstrated_scope: tuple[str, ...]
    evidence: tuple[CausalEvidence, ...]
    known_confounders: tuple[str, ...] = field(default_factory=tuple)
    reverse_causation_tested: bool = False
    intervention_expected: bool = True


@dataclass(frozen=True)
class CausalDecision:
    eligible_to_continue_authority_evaluation: bool
    state: CausalState
    reasons: tuple[str, ...]
    independent_intervention_groups: int
    unresolved_confounders: tuple[str, ...]
    final_authority_granted: bool = False
    path_logic_final_authority: bool = False


def _independent_intervention_groups(evidence: Iterable[CausalEvidence]) -> int:
    groups = {
        (item.method_family, item.lineage)
        for item in evidence
        if item.intervention and not item.contradicted
    }
    return len(groups)


def evaluate_causal_claim(claim: CausalClaim) -> CausalDecision:
    reasons: list[str] = []
    evidence = tuple(claim.evidence)

    if not claim.cause_subject or not claim.effect_subject:
        reasons.append("causal_subject_missing")
    if claim.cause_subject == claim.effect_subject:
        reasons.append("self_causation_claim_requires_special_model")
    if not claim.requested_scope:
        reasons.append("requested_scope_missing")
    if not set(claim.requested_scope).issubset(set(claim.demonstrated_scope)):
        reasons.append("causal_scope_not_demonstrated")
    if not evidence:
        reasons.append("causal_evidence_missing")

    contradicted = any(item.contradicted for item in evidence)
    if contradicted:
        reasons.append("causal_evidence_contradicted")

    unresolved_confounders = tuple(
        confounder
        for confounder in claim.known_confounders
        if not any(confounder in item.confounders_addressed for item in evidence if not item.contradicted)
    )
    if unresolved_confounders:
        reasons.append("known_confounders_unresolved")

    intervention_groups = _independent_intervention_groups(evidence)
    observational_only = bool(evidence) and all(item.observational and not item.intervention for item in evidence)
    if claim.intervention_expected and observational_only:
        reasons.append("observational_association_cannot_certify_causation")
    if claim.intervention_expected and intervention_groups < 1:
        reasons.append("intervention_evidence_missing")
    if intervention_groups == 1 and len(evidence) > 1:
        # Repeated evidence from one intervention lineage is still one causal pressure family.
        reasons.append("causal_independence_limited")
    if not claim.reverse_causation_tested:
        reasons.append("reverse_causation_not_tested")

    if "causal_evidence_contradicted" in reasons or "known_confounders_unresolved" in reasons:
        state = CausalState.CONTESTED
    elif "observational_association_cannot_certify_causation" in reasons or "intervention_evidence_missing" in reasons:
        state = CausalState.OBSERVATIONAL_ONLY
    elif reasons:
        state = CausalState.PROVISIONAL
    else:
        state = CausalState.SURVIVED_INTERVENTION

    return CausalDecision(
        eligible_to_continue_authority_evaluation=not reasons,
        state=state,
        reasons=tuple(reasons),
        independent_intervention_groups=intervention_groups,
        unresolved_confounders=unresolved_confounders,
        final_authority_granted=False,
        path_logic_final_authority=False,
    )


def causal_invariants() -> tuple[str, ...]:
    return (
        "correlation_does_not_grant_causal_authority",
        "causal_direction_requires_pressure_against_reverse_causation",
        "known_confounders_remain_authority_blockers_until_addressed",
        "repeated_same_lineage_interventions_do_not_create_fake_independence",
        "causal_authority_is_scoped_and_revocable",
        "causal_gate_may_block_but_never_grant_final_authority",
        "path_logic_operates_only_after_causal_survival_where_causation_is_required",
    )
