from zero_os.os_isolation import IsolationState, OSIsolationEvidence, evaluate_os_isolation
from zero_os.protected_data_kernel_mediation import KernelMediationDecision
from zero_os.protected_data_promotion import evaluate_protected_data_promotion
from zero_os.protected_key_release import KeyReleaseBrokerDescriptor, KeyReleaseTier
from zero_os.tpm_sealed_key_policy import TPMUnsealDecision


def _kernel() -> KernelMediationDecision:
    return KernelMediationDecision(True, "BREACH_CONTAINMENT_DEMONSTRATED_IN_SCOPE", (), False)


def _broker() -> KeyReleaseBrokerDescriptor:
    return KeyReleaseBrokerDescriptor(
        broker_id="broker",
        tier=KeyReleaseTier.HARDWARE_BACKED,
        separate_process=True,
        separate_os_identity=True,
        runtime_can_read_master_keys=False,
        hardware_backed=True,
        kernel_mediated_ipc=True,
    )


def _os_decision():
    evidence = OSIsolationEvidence(
        state=IsolationState.HARDWARE_ANCHORED,
        runtime_uid="runtime",
        broker_uid="broker",
        distinct_uids=True,
        protected_store_owner_is_broker=True,
        protected_store_mode_blocks_runtime=True,
        broker_socket_peer_credentials_verified=True,
        broker_service_no_new_privileges=True,
        broker_private_tmp=True,
        broker_protect_system_strict=True,
        broker_protect_home=True,
        runtime_ptrace_broker_blocked=True,
        broker_memory_dump_blocked=True,
        runtime_namespace_cannot_mount_protected_store=True,
        runtime_cannot_open_cipher_key_store=True,
        network_egress_default_deny_for_broker=True,
        evidence_provenance=("external-os-audit",),
    )
    return evaluate_os_isolation(evidence)


def _tpm() -> TPMUnsealDecision:
    return TPMUnsealDecision(True, "TPM_UNSEAL_ELIGIBLE_IN_SCOPE", (), False, False)


def _pressure() -> dict:
    return {
        "compromised_process_cannot_read_without_grant": True,
        "read_grant_cannot_export": True,
        "wrong_destination_blocked": True,
        "stale_revision_blocked": True,
        "compromise_revokes_sensitive_path": True,
        "direct_ciphertext_read_does_not_reveal_plaintext": True,
        "runtime_cannot_read_master_key": True,
        "same_privilege_direct_file_bypass_blocked": True,
        "runtime_cannot_ptrace_broker": True,
        "runtime_cannot_mount_protected_store": True,
        "wrong_measured_boot_state_cannot_unseal": True,
    }


def test_full_hardware_containment_can_promote_in_scope():
    result = evaluate_protected_data_promotion(
        capability_registry_report={"read_export_separated": True, "destination_bound_export": True},
        runtime_sink_report={
            "exact_revision_grant_required": True,
            "compromise_shrinks_authority": True,
            "ciphertext_at_rest_required": True,
            "runtime_holds_master_keys": False,
        },
        kernel_mediation_decision=_kernel(),
        key_broker_descriptor=_broker(),
        breach_pressure_report=_pressure(),
        os_isolation_decision=_os_decision(),
        tpm_unseal_decision=_tpm(),
    )
    assert result.promote
    assert result.status == "PROTECTED_DATA_HARDWARE_CONTAINMENT_VERIFIED_IN_SCOPE"


def test_missing_single_exfiltration_pressure_blocks_promotion():
    pressure = _pressure()
    pressure["runtime_cannot_ptrace_broker"] = False
    result = evaluate_protected_data_promotion(
        capability_registry_report={"read_export_separated": True, "destination_bound_export": True},
        runtime_sink_report={
            "exact_revision_grant_required": True,
            "compromise_shrinks_authority": True,
            "ciphertext_at_rest_required": True,
            "runtime_holds_master_keys": False,
        },
        kernel_mediation_decision=_kernel(),
        key_broker_descriptor=_broker(),
        breach_pressure_report=pressure,
        os_isolation_decision=_os_decision(),
        tpm_unseal_decision=_tpm(),
    )
    assert not result.promote
    assert "breach_pressure_failed:runtime_cannot_ptrace_broker" in result.reasons


def test_missing_tpm_evidence_blocks_promotion():
    result = evaluate_protected_data_promotion(
        capability_registry_report={"read_export_separated": True, "destination_bound_export": True},
        runtime_sink_report={
            "exact_revision_grant_required": True,
            "compromise_shrinks_authority": True,
            "ciphertext_at_rest_required": True,
            "runtime_holds_master_keys": False,
        },
        kernel_mediation_decision=_kernel(),
        key_broker_descriptor=_broker(),
        breach_pressure_report=_pressure(),
        os_isolation_decision=_os_decision(),
        tpm_unseal_decision=None,
    )
    assert not result.promote
    assert "tpm_sealed_key_policy_not_verified" in result.reasons
