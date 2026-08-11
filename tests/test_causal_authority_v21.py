from zero_os.causal_authority import CausalClaim, CausalEvidence, CausalState, evaluate_causal_claim
from zero_os.causal_pressure import run_causal_pressure


def test_observational_association_does_not_certify_causation():
    decision = evaluate_causal_claim(CausalClaim(
        claim_id="obs",
        cause_subject="sensor_pattern",
        effect_subject="failure",
        requested_scope=("runtime",),
        demonstrated_scope=("runtime",),
        evidence=(CausalEvidence("e", "logs", "observational", "logs-1"),),
        reverse_causation_tested=False,
    ))
    assert decision.state == CausalState.OBSERVATIONAL_ONLY
    assert not decision.eligible_to_continue_authority_evaluation
    assert not decision.final_authority_granted


def test_known_confounder_blocks_causal_authority():
    decision = evaluate_causal_claim(CausalClaim(
        claim_id="confounded",
        cause_subject="A",
        effect_subject="B",
        requested_scope=("runtime",),
        demonstrated_scope=("runtime",),
        evidence=(CausalEvidence("e", "experiment", "intervention", "i1", observational=False, intervention=True),),
        known_confounders=("C",),
        reverse_causation_tested=True,
    ))
    assert decision.state == CausalState.CONTESTED
    assert "known_confounders_unresolved" in decision.reasons


def test_independent_interventions_can_survive_in_scope_without_granting_final_authority():
    decision = evaluate_causal_claim(CausalClaim(
        claim_id="survived",
        cause_subject="A",
        effect_subject="B",
        requested_scope=("runtime",),
        demonstrated_scope=("runtime",),
        evidence=(
            CausalEvidence("e1", "randomized", "randomized", "r1", observational=False, intervention=True, confounders_addressed=("C",)),
            CausalEvidence("e2", "natural", "natural", "n1", observational=False, intervention=True, counterfactual=True, confounders_addressed=("C",)),
        ),
        known_confounders=("C",),
        reverse_causation_tested=True,
    ))
    assert decision.state == CausalState.SURVIVED_INTERVENTION
    assert decision.eligible_to_continue_authority_evaluation
    assert decision.independent_intervention_groups == 2
    assert not decision.final_authority_granted
    assert not decision.path_logic_final_authority


def test_pressure_suite_preserves_causal_non_authority():
    report = run_causal_pressure()
    assert report["observational_only_blocked"]
    assert report["confounding_blocks"]
    assert report["same_lineage_not_independent"]
    assert report["intervention_survives"]
    assert report["final_authority_granted"] is False
    assert report["master_law_change_justified"] is False
