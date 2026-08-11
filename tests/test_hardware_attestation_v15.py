from zero_os.hardware_attestation import (
    HardwareAttestationBundle,
    HardwareAttestationPolicy,
    PcrValue,
    _pcr_composite,
    verify_hardware_attestation,
)
from zero_os.hardware_recovery_authority import RecoveryAuthorization, evaluate_recovery_authorization


def _bundle(**overrides):
    pcrs = (PcrValue(0, "0" * 64), PcrValue(7, "7" * 64))
    data = {
        "device_identity": "device-1",
        "attestation_key_id": "ak-1",
        "nonce": "challenge-123",
        "quoted_pcrs": pcrs,
        "quoted_pcr_composite_sha256": _pcr_composite(pcrs),
        "event_log_root_sha256": "e" * 64,
        "measured_boot_root_sha256": "b" * 64,
        "monotonic_counter": 9,
        "signature_verified": True,
        "secure_boot_enabled": True,
        "measured_boot_enabled": True,
        "debug_interface_enabled": False,
        "dma_protection_enabled": True,
        "provenance": ("tpm2_quote", "uefi_event_log"),
    }
    data.update(overrides)
    return HardwareAttestationBundle(**data)


def _policy(**overrides):
    data = {
        "expected_device_identity": "device-1",
        "expected_nonce": "challenge-123",
        "allowed_attestation_keys": ("ak-1",),
        "required_pcr_indices": (0, 7),
        "minimum_monotonic_counter": 8,
        "expected_measured_boot_root_sha256": "b" * 64,
        "expected_event_log_root_sha256": "e" * 64,
        "require_dma_protection": True,
    }
    data.update(overrides)
    return HardwareAttestationPolicy(**data)


def test_hardware_attestation_survives_exact_scope_without_granting_authority():
    decision = verify_hardware_attestation(_bundle(), _policy())
    assert decision.verified is True
    assert decision.authority_granted is False
    assert decision.path_logic_final_authority is False


def test_replayed_quote_nonce_is_rejected():
    decision = verify_hardware_attestation(_bundle(nonce="old-challenge"), _policy())
    assert decision.verified is False
    assert "nonce_mismatch_or_missing" in decision.reasons


def test_pcr_composite_rewrite_is_rejected():
    decision = verify_hardware_attestation(_bundle(quoted_pcr_composite_sha256="f" * 64), _policy())
    assert decision.verified is False
    assert "quoted_pcr_composite_mismatch" in decision.reasons


def test_rollback_counter_is_rejected():
    decision = verify_hardware_attestation(_bundle(monotonic_counter=7), _policy())
    assert decision.verified is False
    assert "attestation_rollback_counter_below_policy" in decision.reasons


def test_missing_required_pcr_is_rejected():
    pcrs = (PcrValue(0, "0" * 64),)
    decision = verify_hardware_attestation(
        _bundle(quoted_pcrs=pcrs, quoted_pcr_composite_sha256=_pcr_composite(pcrs)),
        _policy(),
    )
    assert decision.verified is False
    assert "required_pcr_missing:7" in decision.reasons


def test_recovery_requires_failed_boot_and_independent_authority():
    failed = verify_hardware_attestation(_bundle(nonce="wrong"), _policy())
    authorization = RecoveryAuthorization(
        recovery_id="rec-1",
        device_identity="device-1",
        target_boot_root_sha256="c" * 64,
        target_firmware_version=5,
        current_monotonic_counter=9,
        next_monotonic_counter=10,
        signer_ids=("recovery-root",),
        provenance=("offline-recovery-manifest",),
        rollback_reference="snapshot-9",
        independent_evaluator_ids=("recovery-witness",),
    )
    decision = evaluate_recovery_authorization(
        authorization,
        failed_boot_attestation=failed,
        expected_device_identity="device-1",
        allowed_recovery_signers=("recovery-root",),
    )
    assert decision.allowed is True
    assert decision.runtime_can_rewrite_trust_root is False


def test_runtime_cannot_self_authorize_recovery():
    failed = verify_hardware_attestation(_bundle(nonce="wrong"), _policy())
    authorization = RecoveryAuthorization(
        recovery_id="rec-2",
        device_identity="device-1",
        target_boot_root_sha256="c" * 64,
        target_firmware_version=5,
        current_monotonic_counter=9,
        next_monotonic_counter=10,
        signer_ids=("zero-os-runtime",),
        provenance=("runtime",),
        rollback_reference="snapshot-9",
        independent_evaluator_ids=("zero-os-runtime",),
    )
    decision = evaluate_recovery_authorization(
        authorization,
        failed_boot_attestation=failed,
        expected_device_identity="device-1",
        allowed_recovery_signers=("zero-os-runtime",),
    )
    assert decision.allowed is False
    assert "ordinary_runtime_cannot_authorize_or_self_evaluate_recovery" in decision.reasons
