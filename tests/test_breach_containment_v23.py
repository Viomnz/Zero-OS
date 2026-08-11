from zero_os.protected_data_cipher import decrypt_bytes, encrypt_bytes
from zero_os.protected_data_kernel_mediation import KernelMediationEvidence, MediationState, evaluate_kernel_mediation
from zero_os.protected_data_promotion import evaluate_protected_data_promotion
from zero_os.protected_key_release import KeyReleaseBrokerDescriptor, KeyReleaseRequest, KeyReleaseTier, development_descriptor, evaluate_key_release


def _prod_broker() -> KeyReleaseBrokerDescriptor:
    return KeyReleaseBrokerDescriptor(
        broker_id="broker-1",
        tier=KeyReleaseTier.OS_PROTECTED,
        separate_process=True,
        separate_os_identity=True,
        runtime_can_read_master_keys=False,
        hardware_backed=False,
        kernel_mediated_ipc=True,
    )


def _kernel_ok():
    return evaluate_kernel_mediation(KernelMediationEvidence(
        state=MediationState.KERNEL_MEDIATED,
        protected_store_not_readable_by_runtime_uid=True,
        plaintext_path_absent=True,
        broker_ipc_identity_enforced=True,
        ptrace_or_process_memory_escape_blocked=True,
        removable_media_sink_mediated=True,
        network_sink_mediated=True,
        clipboard_sink_mediated=True,
        ipc_sink_mediated=True,
        same_privilege_bypass_tests_passed=True,
        evidence_provenance=("linux-lsm-test", "broker-uid-test"),
    ))


def test_ciphertext_at_rest_does_not_embed_plaintext_and_binds_revision():
    key = b"k" * 32
    plaintext = b"top-secret-zero-os-data"
    container = encrypt_bytes(data_id="secret-1", content_revision="rev-1", key_id="key-1", plaintext=plaintext, data_key=key)
    assert plaintext not in container.to_json().encode()
    assert decrypt_bytes(container, data_key=key, expected_data_id="secret-1", expected_revision="rev-1", expected_key_id="key-1") == plaintext
    try:
        decrypt_bytes(container, data_key=key, expected_data_id="secret-1", expected_revision="rev-2", expected_key_id="key-1")
    except PermissionError:
        pass
    else:
        raise AssertionError("stale revision must not decrypt")


def test_development_key_broker_cannot_satisfy_production_release():
    request = KeyReleaseRequest("p", "d", "r", "k", "read", "", "g", "a", "pid:1")
    decision = evaluate_key_release(
        descriptor=development_descriptor(),
        request=request,
        data_grant_verified=True,
        capability_verified=True,
        process_compromised=False,
        exact_binding_verified=True,
    )
    assert not decision.release_eligible
    assert "key_broker_not_production_isolated" in decision.reasons


def test_compromised_process_cannot_obtain_key_release_even_with_valid_grant():
    request = KeyReleaseRequest("p", "d", "r", "k", "read", "", "g", "a", "pid:1")
    decision = evaluate_key_release(
        descriptor=_prod_broker(),
        request=request,
        data_grant_verified=True,
        capability_verified=True,
        process_compromised=True,
        exact_binding_verified=True,
    )
    assert not decision.release_eligible
    assert "requesting_process_contested" in decision.reasons


def test_kernel_mediation_requires_all_exfiltration_sinks():
    evidence = KernelMediationEvidence(
        state=MediationState.KERNEL_MEDIATED,
        protected_store_not_readable_by_runtime_uid=True,
        plaintext_path_absent=True,
        broker_ipc_identity_enforced=True,
        ptrace_or_process_memory_escape_blocked=True,
        removable_media_sink_mediated=True,
        network_sink_mediated=False,
        clipboard_sink_mediated=True,
        ipc_sink_mediated=True,
        same_privilege_bypass_tests_passed=True,
        evidence_provenance=("test",),
    )
    verdict = evaluate_kernel_mediation(evidence)
    assert not verdict.containment_demonstrated
    assert "network_not_mediated" in verdict.reasons


def test_promotion_requires_structured_kernel_and_external_broker_evidence():
    capability = {"read_export_separated": True, "destination_bound_export": True}
    runtime = {
        "exact_revision_grant_required": True,
        "compromise_shrinks_authority": True,
        "ciphertext_at_rest_required": True,
        "runtime_holds_master_keys": False,
    }
    pressure = {
        "compromised_process_cannot_read_without_grant": True,
        "read_grant_cannot_export": True,
        "wrong_destination_blocked": True,
        "stale_revision_blocked": True,
        "compromise_revokes_sensitive_path": True,
        "direct_ciphertext_read_does_not_reveal_plaintext": True,
        "runtime_cannot_read_master_key": True,
        "same_privilege_direct_file_bypass_blocked": True,
    }
    blocked = evaluate_protected_data_promotion(
        capability_registry_report=capability,
        runtime_sink_report=runtime,
        kernel_mediation_decision=None,
        key_broker_descriptor=development_descriptor(),
        breach_pressure_report=pressure,
    )
    assert not blocked.promote

    promoted = evaluate_protected_data_promotion(
        capability_registry_report=capability,
        runtime_sink_report=runtime,
        kernel_mediation_decision=_kernel_ok(),
        key_broker_descriptor=_prod_broker(),
        breach_pressure_report=pressure,
    )
    assert promoted.promote
    assert promoted.status == "PROTECTED_DATA_CONTAINMENT_VERIFIED_IN_SCOPE"
