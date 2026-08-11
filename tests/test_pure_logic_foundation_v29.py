from zero_os.foundation_compatibility import CompatibilityState, classify_architecture, legacy_may_override_foundation
from zero_os.pure_logic_foundation import (
    AuthorityState,
    ExecutionState,
    MasterLaw,
    foundation_manifest,
    validate_foundation_manifest,
)


def test_current_foundation_has_exactly_six_master_laws_and_is_revisable():
    manifest = foundation_manifest()
    assert set(manifest["master_laws"]) == {law.value for law in MasterLaw}
    assert manifest["master_laws_final"] is False
    assert manifest["foundation_revisable"] is True


def test_foundation_cannot_self_certify_or_grant_final_authority():
    manifest = foundation_manifest()
    ok, reasons = validate_foundation_manifest(manifest)
    assert ok, reasons
    assert manifest["final_authority_granted"] is False
    assert manifest["self_certified"] is False
    assert manifest["terminal_correct_state_exists"] is False


def test_tampered_final_master_law_claim_is_rejected():
    manifest = foundation_manifest()
    manifest["master_laws_final"] = True
    ok, reasons = validate_foundation_manifest(manifest)
    assert not ok
    assert "master_laws_cannot_be_final" in reasons


def test_tampered_self_certification_is_rejected():
    manifest = foundation_manifest()
    manifest["self_certified"] = True
    ok, reasons = validate_foundation_manifest(manifest)
    assert not ok
    assert "foundation_manifest_cannot_self_certify" in reasons


def test_pipeline_has_no_terminal_correct_state():
    manifest = foundation_manifest()
    assert "CORRECT" not in manifest["pipeline"]
    assert manifest["pipeline"][0] == "REALITY"
    assert manifest["pipeline"][-1] == "REALITY"


def test_relations_time_and_causality_are_first_class_authority_subjects():
    kinds = set(foundation_manifest()["authority_subject_kinds"])
    assert {"SUBJECT", "RELATION", "JOINT_STATE", "TEMPORAL_STATE", "CAUSAL_CLAIM"} <= kinds


def test_authority_is_scoped_and_time_dependent_not_global_scalar():
    manifest = foundation_manifest()
    assert manifest["authority_form"] == "A(x,D,t)=f(E,P,S,C,Q,R)"
    assert manifest["authority_is_global_scalar"] is False
    tampered = dict(manifest)
    tampered["authority_is_global_scalar"] = True
    ok, reasons = validate_foundation_manifest(tampered)
    assert not ok
    assert "authority_cannot_be_global_unscoped_scalar" in reasons


def test_zero_execution_state_is_explicit_and_nonfinal():
    manifest = foundation_manifest()
    assert ExecutionState.ZERO.value in manifest["execution_states"]
    assert manifest["zero_state"]["final_authority"] is False
    assert manifest["zero_state"]["resource_cost_still_applies"] is True


def test_prediction_cannot_self_upgrade_into_intervention_authority():
    manifest = foundation_manifest()
    assert manifest["causal_boundary"]["predictive_success_implies_intervention_authority"] is False
    assert manifest["causal_boundary"]["intervention_requires_stronger_causal_evidence"] is True
    manifest["causal_boundary"]["predictive_success_implies_intervention_authority"] = True
    ok, reasons = validate_foundation_manifest(manifest)
    assert not ok
    assert "prediction_cannot_self_upgrade_to_intervention_authority" in reasons


def test_consciousness_boundary_stays_open_hypothesis():
    manifest = foundation_manifest()
    boundary = manifest["consciousness_boundary"]
    assert boundary["self_modeling_equals_functional_self_awareness"] is False
    assert boundary["functional_self_awareness_equals_phenomenal_consciousness"] is False
    assert boundary["phenomenal_consciousness_status"] == "OPEN_HYPOTHESIS"


def test_nonfinal_mechanisms_remain_nonfinal():
    mechanisms = set(foundation_manifest()["non_final_mechanisms"])
    assert "PATH_LAW" in mechanisms
    assert "WATER_LOGIC" in mechanisms
    assert "IMMUNE_BEACON" in mechanisms
    assert "SCOPE_CERTIFIER" in mechanisms
    assert "ZERO_EXECUTION_STATE" in mechanisms


def test_legacy_conscious_machine_is_evidence_not_foundation():
    result = classify_architecture("conscious_machine_architecture")
    assert result.state == CompatibilityState.LEGACY_EVIDENCE_ONLY
    assert not result.may_define_pure_logic
    assert not result.may_grant_final_authority
    assert not legacy_may_override_foundation("conscious_machine_architecture")


def test_old_perfect_omni_singular_cannot_override_current_foundation():
    for component in ("perfect_zero", "omni_zero", "singular_zero"):
        result = classify_architecture(component)
        assert result.state == CompatibilityState.LEGACY_EVIDENCE_ONLY
        assert not legacy_may_override_foundation(component)


def test_legacy_cure_beacon_is_pressure_evidence_only():
    result = classify_architecture("legacy_cure_recursion_beacon")
    assert result.state == CompatibilityState.LEGACY_EVIDENCE_ONLY
    assert "recursion_pass_is_pressure_evidence_only" in result.reasons


def test_authority_state_retains_revocation_and_history():
    assert AuthorityState.CONTESTED.value == "CONTESTED"
    assert AuthorityState.REVOKED.value == "REVOKED"
    assert AuthorityState.HISTORICAL.value == "HISTORICAL"
