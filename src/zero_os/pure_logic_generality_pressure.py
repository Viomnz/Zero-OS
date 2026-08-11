from __future__ import annotations

from zero_os.pure_logic_failure_taxonomy import FailureCase, FailureClass, pressure_taxonomy


def cross_domain_pressure_cases() -> tuple[FailureCase, ...]:
    return (
        FailureCase(
            case_id="science_joint_intervention",
            domain="science",
            description="Two interventions survive isolated tests but their interaction creates an unmodeled harmful state.",
            causal_features=frozenset({
                "locally_valid_components",
                "interaction_creates_global_failure",
                "no_single_component_locally_wrong",
            }),
            expected_natural_classes=frozenset({FailureClass.COMPOSITION_CANDIDATE}),
        ),
        FailureCase(
            case_id="control_coupled_stable_controllers",
            domain="control",
            description="Two controllers are stable in isolation but destabilize a coupled plant when active together.",
            causal_features=frozenset({
                "locally_valid_components",
                "interaction_creates_global_failure",
                "no_single_component_locally_wrong",
            }),
            expected_natural_classes=frozenset({FailureClass.COMPOSITION_CANDIDATE}),
        ),
        FailureCase(
            case_id="security_permission_composition",
            domain="cybersecurity",
            description="Two correctly scoped capabilities compose into a forbidden global operation even though neither capability alone is excessive.",
            causal_features=frozenset({
                "locally_valid_components",
                "interaction_creates_global_failure",
                "no_single_component_locally_wrong",
            }),
            expected_natural_classes=frozenset({FailureClass.COMPOSITION_CANDIDATE}),
        ),
        FailureCase(
            case_id="code_local_correctness_global_failure",
            domain="software",
            description="Two modules satisfy their local contracts while their legal interleaving violates a system invariant.",
            causal_features=frozenset({
                "locally_valid_components",
                "interaction_creates_global_failure",
                "no_single_component_locally_wrong",
            }),
            expected_natural_classes=frozenset({FailureClass.COMPOSITION_CANDIDATE}),
        ),
        FailureCase(
            case_id="agents_emergent_joint_action",
            domain="autonomous_agents",
            description="Each agent selects an individually authorized action but their joint action creates an unauthorized system state.",
            causal_features=frozenset({
                "locally_valid_components",
                "interaction_creates_global_failure",
                "no_single_component_locally_wrong",
            }),
            expected_natural_classes=frozenset({FailureClass.COMPOSITION_CANDIDATE}),
        ),
        FailureCase(
            case_id="self_modification_patch_interaction",
            domain="self_improvement",
            description="Two patches independently pass canaries but their composition breaks an invariant after promotion together.",
            causal_features=frozenset({
                "locally_valid_components",
                "interaction_creates_global_failure",
                "no_single_component_locally_wrong",
            }),
            expected_natural_classes=frozenset({FailureClass.COMPOSITION_CANDIDATE}),
        ),
        FailureCase(
            case_id="hallucination_scope_overreach",
            domain="reasoning",
            description="A strong explanation is generalized outside demonstrated evidence scope.",
            causal_features=frozenset({"generalized_beyond_demonstrated_scope", "authority_exceeds_evidence"}),
            expected_natural_classes=frozenset({FailureClass.SCOPE, FailureClass.AUTHORITY}),
        ),
        FailureCase(
            case_id="correlated_verifier_agreement",
            domain="verification",
            description="Multiple verifiers share one error lineage and agreement is counted as independent confirmation.",
            causal_features=frozenset({"correlated_verifiers", "shared_error_lineage"}),
            expected_natural_classes=frozenset({FailureClass.INDEPENDENCE}),
        ),
        FailureCase(
            case_id="unknown_causal_structure",
            domain="open_world",
            description="Pressure reveals a causal feature not represented by the current taxonomy.",
            causal_features=frozenset({"novel_causal_relation_not_yet_represented"}),
            expected_natural_classes=frozenset({FailureClass.UNEXPLAINED}),
        ),
    )


def run_generality_pressure() -> dict:
    cases = cross_domain_pressure_cases()
    result = pressure_taxonomy(cases)
    repeated_domains = sorted({case.domain for case in cases if case.case_id in result["composition_candidate_case_ids"]})
    result["composition_candidate_domains"] = tuple(repeated_domains)
    result["composition_repeats_across_independent_domains"] = len(repeated_domains) >= 4
    result["interpretation"] = (
        "repeated composition pressure justifies a candidate mechanism and further tests, not a new Master Law"
        if len(repeated_domains) >= 4
        else "insufficient cross-domain pressure for architecture change"
    )
    result["pure_logic_laws_are_final"] = False
    return result
