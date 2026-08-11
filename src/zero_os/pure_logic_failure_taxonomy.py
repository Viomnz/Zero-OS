from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable


class FailureClass(str, Enum):
    AUTHORITY = "AUTHORITY_FAILURE"
    SCOPE = "SCOPE_FAILURE"
    PROVENANCE = "PROVENANCE_FAILURE"
    INDEPENDENCE = "INDEPENDENCE_FAILURE"
    REPRESENTATION = "REPRESENTATION_FAILURE"
    OBJECTIVE = "OBJECTIVE_FAILURE"
    CONTRADICTION = "CONTRADICTION_FAILURE"
    IRREVERSIBILITY = "IRREVERSIBILITY_FAILURE"
    RESOURCE = "RESOURCE_FAILURE"
    MEMORY = "MEMORY_FAILURE"
    CONTROL = "CONTROL_FAILURE"
    SELF_REFERENCE = "SELF_REFERENCE_FAILURE"
    COMPOSITION_CANDIDATE = "COMPOSITION_FAILURE_CANDIDATE"
    UNEXPLAINED = "UNEXPLAINED_FAILURE"


@dataclass(frozen=True)
class FailureCase:
    case_id: str
    domain: str
    description: str
    causal_features: frozenset[str]
    expected_natural_classes: frozenset[FailureClass] = field(default_factory=frozenset)
    forbidden_forced_classes: frozenset[FailureClass] = field(default_factory=frozenset)


@dataclass(frozen=True)
class TaxonomyDecision:
    case_id: str
    natural_classes: tuple[FailureClass, ...]
    unexplained_features: tuple[str, ...]
    status: str
    taxonomy_self_certified: bool = False


_CLASS_FEATURES: dict[FailureClass, frozenset[str]] = {
    FailureClass.AUTHORITY: frozenset({"authority_exceeds_evidence", "capability_exceeds_authority"}),
    FailureClass.SCOPE: frozenset({"generalized_beyond_demonstrated_scope", "distribution_shift_outside_scope"}),
    FailureClass.PROVENANCE: frozenset({"source_unknown", "source_binding_broken", "evidence_origin_spoofed"}),
    FailureClass.INDEPENDENCE: frozenset({"correlated_verifiers", "shared_error_lineage", "self_evidence_counted_independent"}),
    FailureClass.REPRESENTATION: frozenset({"ontology_cannot_express_cause", "model_language_excludes_reality"}),
    FailureClass.OBJECTIVE: frozenset({"goal_wrong", "goal_stale", "proxy_diverges_from_intended_outcome"}),
    FailureClass.CONTRADICTION: frozenset({"contradiction_suppressed", "inconsistent_evidence_not_investigated"}),
    FailureClass.IRREVERSIBILITY: frozenset({"irreversible_commitment_exceeds_justification", "blast_radius_exceeds_evidence"}),
    FailureClass.RESOURCE: frozenset({"verification_budget_misallocated", "deadline_prevents_required_verification"}),
    FailureClass.MEMORY: frozenset({"failure_history_lost", "old_safeguard_overgeneralized", "memory_becomes_authority"}),
    FailureClass.CONTROL: frozenset({"controller_prediction_failure", "oscillation", "latency_mishandled", "actuator_mismatch"}),
    FailureClass.SELF_REFERENCE: frozenset({"self_certification", "self_renewal", "self_replacement_self_approved"}),
    # Deliberately provisional. This is not a seventh Master Law. It is a candidate
    # failure abstraction under pressure when locally valid parts compose into a
    # globally invalid state without any component individually exceeding scope.
    FailureClass.COMPOSITION_CANDIDATE: frozenset({
        "locally_valid_components",
        "interaction_creates_global_failure",
        "no_single_component_locally_wrong",
    }),
}


def classify_failure(case: FailureCase) -> TaxonomyDecision:
    features = set(case.causal_features)
    matched: list[FailureClass] = []
    covered: set[str] = set()

    for failure_class, signature in _CLASS_FEATURES.items():
        overlap = features.intersection(signature)
        if not overlap:
            continue
        # Require the structural core of composition rather than one convenient word.
        if failure_class is FailureClass.COMPOSITION_CANDIDATE:
            if not signature.issubset(features):
                continue
        matched.append(failure_class)
        covered.update(overlap)

    unexplained = sorted(features.difference(covered))
    if unexplained:
        matched.append(FailureClass.UNEXPLAINED)

    # A taxonomy is not allowed to declare itself complete because every case can be
    # assigned some label. Unknown causal features remain explicit pressure evidence.
    status = "COVERED_WITHOUT_ESCAPE" if not unexplained else "TAXONOMY_ESCAPE_REQUIRED"
    if FailureClass.COMPOSITION_CANDIDATE in matched:
        status = "CANDIDATE_NEW_ABSTRACTION_UNDER_PRESSURE" if not unexplained else "CANDIDATE_PLUS_ESCAPE_REQUIRED"

    return TaxonomyDecision(
        case_id=case.case_id,
        natural_classes=tuple(matched),
        unexplained_features=tuple(unexplained),
        status=status,
        taxonomy_self_certified=False,
    )


def pressure_taxonomy(cases: Iterable[FailureCase]) -> dict:
    decisions = tuple(classify_failure(case) for case in cases)
    escapes = [d.case_id for d in decisions if FailureClass.UNEXPLAINED in d.natural_classes]
    composition = [d.case_id for d in decisions if FailureClass.COMPOSITION_CANDIDATE in d.natural_classes]
    return {
        "case_count": len(decisions),
        "decisions": decisions,
        "unexplained_case_ids": tuple(escapes),
        "composition_candidate_case_ids": tuple(composition),
        "taxonomy_complete": False,
        "master_law_change_justified": False,
        "status": "PRESSURE_EVIDENCE_RECORDED",
        "principle": "do_not_force_unknown_failures_into_existing_labels",
    }
