from zero_os.composition_pressure_gate import AuthorizedPart, CompositionRequest, evaluate_composition
from zero_os.relational_authority import (
    RelationAuthorityContract,
    RelationAuthorityState,
    RelationEvidence,
    RelationSubject,
    evaluate_relation_authority,
)
from zero_os.relational_generality_pressure import run_relational_generality_pressure


def _contract(*, contradicted=False, groups=2):
    evidence = [
        RelationEvidence("e1", "probe", "simulation", "lineage-a", ("joint:on",), True, True, True, contradicted),
    ]
    if groups > 1:
        evidence.append(RelationEvidence("e2", "probe2", "empirical", "lineage-b", ("joint:on",), True, True, True, False))
    return RelationAuthorityContract(
        relation=RelationSubject("rel-1", ("A", "B"), "interaction", "r1", "joint:on"),
        state=RelationAuthorityState.PROVISIONAL,
        demonstrated_joint_scope=("joint:on",),
        evidence=tuple(evidence),
        parent_authority_ids=("auth-a", "auth-b"),
    )


def _composition(relation):
    return CompositionRequest(
        composition_id="rel-1",
        parts=(
            AuthorizedPart("A", "auth-a", ("local:a",), True, "r1"),
            AuthorizedPart("B", "auth-b", ("local:b",), True, "r1"),
        ),
        requested_joint_state="joint:on",
        certified_joint_states=("joint:on",),
        joint_invariants_passed=True,
        interaction_model_available=True,
        reversible=True,
        uncertainty=0.05,
        relation_authority=relation,
    )


def test_local_authority_does_not_certify_relation():
    decision = evaluate_composition(_composition(None))
    assert not decision.eligible_to_continue_authority_evaluation
    assert "relation_authority_missing" in decision.reasons
    assert decision.final_authority_granted is False


def test_relation_requires_independent_evidence_groups():
    decision = evaluate_relation_authority(_contract(groups=1))
    assert not decision.survived
    assert "insufficient_independent_relation_evidence" in decision.reasons


def test_contradicted_relation_revokes_composition_clearance():
    decision = evaluate_composition(_composition(_contract(contradicted=True)))
    assert not decision.eligible_to_continue_authority_evaluation
    assert any("relation_evidence_contradicted" in reason for reason in decision.reasons)


def test_survived_relation_only_allows_continuing_authority_evaluation():
    decision = evaluate_composition(_composition(_contract()))
    assert decision.eligible_to_continue_authority_evaluation
    assert decision.relation_authority_survived
    assert decision.final_authority_granted is False
    assert decision.path_logic_final_authority is False


def test_relational_derivation_repeats_across_domains_without_seventh_law():
    report = run_relational_generality_pressure()
    assert report["relation_as_first_class_subject_repeated_across_domains"]
    assert report["composition_requires_seventh_master_law"] is False
    assert report["master_law_change_justified"] is False
    assert report["external_validation_required"] is True
