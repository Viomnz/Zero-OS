from zero_os.composition_pressure_gate import AuthorizedPart, CompositionRequest, CompositionState, evaluate_composition
from zero_os.pure_logic_failure_taxonomy import FailureClass, classify_failure
from zero_os.pure_logic_generality_pressure import cross_domain_pressure_cases, run_generality_pressure
from zero_os.pure_logic_generality_promotion import evaluate_generality_research_promotion


def test_existing_taxonomy_is_not_self_certified_complete():
    result = run_generality_pressure()
    assert result["taxonomy_complete"] is False
    assert result["pure_logic_laws_are_final"] is False
    assert "unknown_causal_structure" in result["unexplained_case_ids"]


def test_composition_failure_repeats_across_multiple_domains_without_becoming_new_law():
    result = run_generality_pressure()
    assert result["composition_repeats_across_independent_domains"] is True
    assert len(result["composition_candidate_domains"]) >= 4
    assert result["master_law_change_justified"] is False


def test_known_scope_and_independence_failures_still_map_naturally():
    cases = {case.case_id: case for case in cross_domain_pressure_cases()}
    scope = classify_failure(cases["hallucination_scope_overreach"])
    independence = classify_failure(cases["correlated_verifier_agreement"])
    assert FailureClass.SCOPE in scope.natural_classes
    assert FailureClass.AUTHORITY in scope.natural_classes
    assert FailureClass.INDEPENDENCE in independence.natural_classes
    assert FailureClass.UNEXPLAINED not in independence.natural_classes


def test_unknown_causal_feature_is_preserved_instead_of_forced_into_existing_label():
    cases = {case.case_id: case for case in cross_domain_pressure_cases()}
    decision = classify_failure(cases["unknown_causal_structure"])
    assert FailureClass.UNEXPLAINED in decision.natural_classes
    assert "novel_causal_relation_not_yet_represented" in decision.unexplained_features
    assert decision.taxonomy_self_certified is False


def _part(name: str) -> AuthorizedPart:
    return AuthorizedPart(
        part_id=name,
        authority_id=f"authority:{name}",
        demonstrated_scope=(f"scope:{name}",),
        local_invariants_passed=True,
        state_revision="r1",
    )


def test_local_authority_does_not_imply_joint_authority():
    decision = evaluate_composition(
        CompositionRequest(
            composition_id="joint",
            parts=(_part("a"), _part("b")),
            requested_joint_state="a+b",
            certified_joint_states=(),
            joint_invariants_passed=False,
            interaction_model_available=False,
            reversible=True,
            uncertainty=0.1,
        )
    )
    assert decision.eligible_to_continue_authority_evaluation is False
    assert decision.state in {CompositionState.BLOCK, CompositionState.INVESTIGATE}
    assert decision.final_authority_granted is False


def test_joint_state_must_survive_its_own_scope_and_invariants():
    decision = evaluate_composition(
        CompositionRequest(
            composition_id="joint",
            parts=(_part("a"), _part("b")),
            requested_joint_state="a+b",
            certified_joint_states=("a+b",),
            joint_invariants_passed=True,
            interaction_model_available=True,
            reversible=True,
            uncertainty=0.1,
        )
    )
    assert decision.eligible_to_continue_authority_evaluation is True
    assert decision.state is CompositionState.CLEAR
    assert decision.final_authority_granted is False
    assert decision.path_logic_final_authority is False


def test_irreversible_composition_under_uncertainty_fails_closed():
    decision = evaluate_composition(
        CompositionRequest(
            composition_id="joint",
            parts=(_part("a"), _part("b")),
            requested_joint_state="a+b",
            certified_joint_states=("a+b",),
            joint_invariants_passed=True,
            interaction_model_available=True,
            reversible=False,
            uncertainty=0.8,
        )
    )
    assert decision.state is CompositionState.BLOCK
    assert "irreversible_composition_under_excess_uncertainty" in decision.reasons


def test_generality_promotion_remains_blocked_without_external_pressure():
    decision = evaluate_generality_research_promotion()
    assert decision["promotion_permitted"] is False
    assert "independent_external_cases_missing" in decision["blockers"]
    assert decision["composition_candidate_promoted_to_master_law"] is False
