from __future__ import annotations

from zero_os.causal_authority import CausalClaim, CausalEvidence, evaluate_causal_claim


def run_causal_pressure() -> dict:
    cases = {}

    observational = CausalClaim(
        claim_id="obs_only",
        cause_subject="A",
        effect_subject="B",
        requested_scope=("system",),
        demonstrated_scope=("system",),
        evidence=(CausalEvidence("e1", "telemetry", "observational", "lineage-1"),),
        known_confounders=(),
        reverse_causation_tested=False,
    )
    cases["observational_only"] = evaluate_causal_claim(observational)

    confounded = CausalClaim(
        claim_id="confounded",
        cause_subject="A",
        effect_subject="B",
        requested_scope=("system",),
        demonstrated_scope=("system",),
        evidence=(CausalEvidence("e2", "experiment", "intervention", "lineage-2", observational=False, intervention=True),),
        known_confounders=("C",),
        reverse_causation_tested=True,
    )
    cases["unresolved_confounder"] = evaluate_causal_claim(confounded)

    same_lineage = CausalClaim(
        claim_id="same_lineage",
        cause_subject="A",
        effect_subject="B",
        requested_scope=("system",),
        demonstrated_scope=("system",),
        evidence=(
            CausalEvidence("e3", "experiment-1", "intervention", "shared", observational=False, intervention=True),
            CausalEvidence("e4", "experiment-2", "intervention", "shared", observational=False, intervention=True),
        ),
        reverse_causation_tested=True,
    )
    cases["same_lineage"] = evaluate_causal_claim(same_lineage)

    survived = CausalClaim(
        claim_id="survived",
        cause_subject="A",
        effect_subject="B",
        requested_scope=("system",),
        demonstrated_scope=("system",),
        evidence=(
            CausalEvidence("e5", "randomized", "randomized_intervention", "lineage-r", observational=False, intervention=True, confounders_addressed=("C",)),
            CausalEvidence("e6", "natural", "natural_experiment", "lineage-n", observational=False, intervention=True, counterfactual=True, confounders_addressed=("C",)),
        ),
        known_confounders=("C",),
        reverse_causation_tested=True,
    )
    cases["survived"] = evaluate_causal_claim(survived)

    return {
        "cases": cases,
        "observational_only_blocked": not cases["observational_only"].eligible_to_continue_authority_evaluation,
        "confounding_blocks": not cases["unresolved_confounder"].eligible_to_continue_authority_evaluation,
        "same_lineage_not_independent": cases["same_lineage"].independent_intervention_groups == 1,
        "intervention_survives": cases["survived"].eligible_to_continue_authority_evaluation,
        "final_authority_granted": False,
        "master_law_change_justified": False,
        "interpretation": "causal authority is a derived mechanism under Reality, Survival, Plurality, Investigation, Path, and Resource Laws",
    }
