from __future__ import annotations

from dataclasses import asdict, dataclass, field

from zero_os.hardware_attestation import HardwareAttestationDecision


@dataclass(frozen=True)
class RecoveryAuthorization:
    recovery_id: str
    device_identity: str
    target_boot_root_sha256: str
    target_firmware_version: int
    current_monotonic_counter: int
    next_monotonic_counter: int
    signer_ids: tuple[str, ...]
    provenance: tuple[str, ...]
    rollback_reference: str
    independent_evaluator_ids: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class RecoveryDecision:
    allowed: bool
    status: str
    reasons: tuple[str, ...]
    authority_granted_by_path_logic: bool = False
    runtime_can_rewrite_trust_root: bool = False


def evaluate_recovery_authorization(
    authorization: RecoveryAuthorization,
    *,
    failed_boot_attestation: HardwareAttestationDecision,
    expected_device_identity: str,
    allowed_recovery_signers: tuple[str, ...],
    runtime_actor_id: str = "zero-os-runtime",
) -> RecoveryDecision:
    reasons: list[str] = []
    if failed_boot_attestation.verified:
        reasons.append("recovery_not_justified_by_failed_or_contested_boot")
    if authorization.device_identity != expected_device_identity:
        reasons.append("recovery_device_identity_mismatch")
    if not authorization.provenance:
        reasons.append("recovery_provenance_missing")
    if not authorization.target_boot_root_sha256:
        reasons.append("recovery_target_boot_root_missing")
    if not authorization.rollback_reference:
        reasons.append("recovery_rollback_reference_missing")
    if authorization.next_monotonic_counter <= authorization.current_monotonic_counter:
        reasons.append("recovery_monotonic_counter_not_advanced")
    if authorization.target_firmware_version < 0:
        reasons.append("recovery_target_version_invalid")

    signers = {str(item) for item in authorization.signer_ids if str(item)}
    allowed = {str(item) for item in allowed_recovery_signers if str(item)}
    if not signers:
        reasons.append("recovery_signer_missing")
    elif allowed and not signers.issubset(allowed):
        reasons.append("recovery_signer_not_allowed")

    evaluators = {str(item) for item in authorization.independent_evaluator_ids if str(item)}
    if not evaluators:
        reasons.append("independent_recovery_evaluation_missing")
    if runtime_actor_id in signers or runtime_actor_id in evaluators:
        reasons.append("ordinary_runtime_cannot_authorize_or_self_evaluate_recovery")

    return RecoveryDecision(
        allowed=not reasons,
        status="ELIGIBLE_FOR_PROTECTED_RECOVERY" if not reasons else "BLOCK_RECOVERY",
        reasons=tuple(reasons),
        authority_granted_by_path_logic=False,
        runtime_can_rewrite_trust_root=False,
    )


def recovery_decision_to_dict(decision: RecoveryDecision) -> dict:
    return asdict(decision)
