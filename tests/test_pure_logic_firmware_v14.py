from datetime import datetime, timedelta, timezone

from zero_os.firmware_measured_boot import measured_boot_root
from zero_os.firmware_pure_logic import (
    FirmwareDecisionState,
    FirmwareMeasurement,
    FirmwarePolicy,
    HardwareTrustEvidence,
    evaluate_firmware_boot,
)
from zero_os.firmware_reality_checkpoint import FirmwareCheckpoint, verify_checkpoint_progression
from zero_os.firmware_revision_authority import FirmwareRevisionRequest, evaluate_firmware_revision


def _measurement(component: str, digest: str = "aa" * 32) -> FirmwareMeasurement:
    return FirmwareMeasurement(
        component_id=component,
        digest_sha256=digest,
        expected_digest_sha256=digest,
        source="firmware",
        measured_at_utc=datetime.now(timezone.utc).isoformat(),
        version="1",
        signer_id="root-a",
        signature_verified=True,
        provenance_verified=True,
    )


def _hardware(counter: int = 10) -> HardwareTrustEvidence:
    return HardwareTrustEvidence(
        device_identity="device-1",
        hardware_root_present=True,
        secure_boot_enabled=True,
        measured_boot_supported=True,
        monotonic_counter=counter,
        debug_interface_enabled=False,
        dma_protection_enabled=True,
        provenance=("tpm", "firmware"),
    )


def _policy() -> FirmwarePolicy:
    return FirmwarePolicy(
        required_components=("firmware", "bootloader", "kernel", "authority_kernel"),
        minimum_monotonic_counter=10,
        allowed_signers=("root-a",),
        require_dma_protection=True,
    )


def test_firmware_allows_only_verified_required_measurements():
    rows = tuple(_measurement(x) for x in _policy().required_components)
    decision = evaluate_firmware_boot(policy=_policy(), hardware=_hardware(), measurements=rows)
    assert decision.allowed is True
    assert decision.state == FirmwareDecisionState.ALLOW_BOOT
    assert decision.path_logic_final_authority is False
    assert decision.firmware_self_certification_permitted is False


def test_digest_mismatch_requires_recovery_not_confident_boot():
    rows = list(_measurement(x) for x in _policy().required_components)
    rows[2] = FirmwareMeasurement(**{**rows[2].__dict__, "digest_sha256": "bb" * 32})
    decision = evaluate_firmware_boot(policy=_policy(), hardware=_hardware(), measurements=rows)
    assert decision.allowed is False
    assert decision.state == FirmwareDecisionState.RECOVERY_REQUIRED


def test_rollback_counter_blocks_boot():
    rows = tuple(_measurement(x) for x in _policy().required_components)
    decision = evaluate_firmware_boot(policy=_policy(), hardware=_hardware(counter=9), measurements=rows)
    assert decision.allowed is False
    assert "rollback_counter_below_policy" in decision.reasons


def test_measured_boot_root_is_evidence_not_authority():
    rows = tuple(_measurement(x) for x in _policy().required_components)
    result = measured_boot_root(rows)
    assert result["ok"] is True
    assert result["authority_granted"] is False
    assert result["epistemic_role"] == "measured_boot_evidence_only"


def test_checkpoint_must_advance_monotonically():
    previous = FirmwareCheckpoint("device-1", "a", "b", "c", "d", 5, "witness")
    current = FirmwareCheckpoint("device-1", "a2", "b2", "c2", "d2", 5, "witness")
    result = verify_checkpoint_progression(previous, current)
    assert result["ok"] is False
    assert "monotonic_counter_not_advanced" in result["reasons"]


def test_firmware_revision_cannot_rollback_or_self_certify():
    req = FirmwareRevisionRequest(
        candidate_id="fw-2",
        target="firmware_policy",
        proposer_id="firmware-controller",
        provenance=("signed-release",),
        invariant_checks=("boot-model",),
        pressure_results=("fault-injection",),
        independent_evaluators=("external-auditor",),
        rollback_reference="slot-b",
        canary_reference="test-device",
        compatibility_reference="hw-matrix",
        signed_manifest_reference="manifest.sig",
        monotonic_version=2,
        current_monotonic_version=3,
    )
    result = evaluate_firmware_revision(req)
    assert result["allowed_for_isolated_firmware_update_path"] is False
    assert "rollback_or_non_monotonic_firmware_version" in result["reasons"]
    assert result["path_logic_final_authority"] is False
    assert result["final_firmware_signature_authority_granted"] is False
