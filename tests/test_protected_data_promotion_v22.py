from zero_os.protected_data_promotion import evaluate_protected_data_promotion


def _capability():
    return {"read_export_separated": True, "destination_bound_export": True}


def _runtime():
    return {"exact_revision_grant_required": True, "compromise_shrinks_authority": True}


def _pressure():
    return {
        "compromised_process_cannot_read_without_grant": True,
        "read_grant_cannot_export": True,
        "wrong_destination_blocked": True,
        "stale_revision_blocked": True,
        "compromise_revokes_sensitive_path": True,
    }


def test_software_api_mediation_cannot_claim_hack_containment():
    decision = evaluate_protected_data_promotion(
        capability_registry_report=_capability(),
        runtime_sink_report=_runtime(),
        kernel_mediation_report=None,
        breach_pressure_report=_pressure(),
    )
    assert decision.promote is False
    assert "kernel_or_hardware_data_mediation_not_verified" in decision.reasons


def test_full_containment_requires_structured_kernel_evidence():
    kernel = {
        "verified": True,
        "filesystem_mediation": True,
        "key_release_isolated": True,
        "export_sinks_mediated": True,
        "same_privilege_bypass_tested": True,
        "authority_granted": False,
    }
    decision = evaluate_protected_data_promotion(
        capability_registry_report=_capability(),
        runtime_sink_report=_runtime(),
        kernel_mediation_report=kernel,
        breach_pressure_report=_pressure(),
    )
    assert decision.promote is True
    assert decision.status == "PROTECTED_DATA_CONTAINMENT_VERIFIED_IN_SCOPE"


def test_kernel_report_cannot_grant_authority():
    kernel = {
        "verified": True,
        "filesystem_mediation": True,
        "key_release_isolated": True,
        "export_sinks_mediated": True,
        "same_privilege_bypass_tested": True,
        "authority_granted": True,
    }
    decision = evaluate_protected_data_promotion(
        capability_registry_report=_capability(),
        runtime_sink_report=_runtime(),
        kernel_mediation_report=kernel,
        breach_pressure_report=_pressure(),
    )
    assert decision.promote is False
    assert "kernel_mediation_report_attempted_authority_laundering" in decision.reasons
