from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TPMSealedKeyPolicy:
    key_id: str
    expected_device_id: str
    expected_pcr_digest: str
    expected_measured_boot_root: str
    minimum_monotonic_counter: int
    broker_identity: str
    require_secure_boot: bool = True
    require_debug_disabled: bool = True


@dataclass(frozen=True)
class TPMUnsealEvidence:
    device_id: str
    pcr_digest: str
    measured_boot_root: str
    monotonic_counter: int
    broker_identity: str
    secure_boot_enabled: bool
    debug_disabled: bool
    quote_fresh: bool
    quote_signature_verified: bool
    evidence_provenance: tuple[str, ...]
    contradictions: tuple[str, ...] = ()


@dataclass(frozen=True)
class TPMUnsealDecision:
    unseal_eligible: bool
    status: str
    reasons: tuple[str, ...]
    key_released: bool = False
    authority_granted: bool = False


def evaluate_tpm_unseal(policy: TPMSealedKeyPolicy, evidence: TPMUnsealEvidence) -> TPMUnsealDecision:
    reasons: list[str] = []
    if not policy.key_id:
        reasons.append("sealed_key_id_missing")
    if evidence.device_id != policy.expected_device_id:
        reasons.append("sealed_key_device_mismatch")
    if evidence.pcr_digest != policy.expected_pcr_digest:
        reasons.append("sealed_key_pcr_mismatch")
    if evidence.measured_boot_root != policy.expected_measured_boot_root:
        reasons.append("sealed_key_measured_boot_root_mismatch")
    if int(evidence.monotonic_counter) < int(policy.minimum_monotonic_counter):
        reasons.append("sealed_key_rollback_counter")
    if evidence.broker_identity != policy.broker_identity:
        reasons.append("sealed_key_broker_identity_mismatch")
    if policy.require_secure_boot and not evidence.secure_boot_enabled:
        reasons.append("sealed_key_secure_boot_missing")
    if policy.require_debug_disabled and not evidence.debug_disabled:
        reasons.append("sealed_key_debug_interface_enabled")
    if not evidence.quote_fresh:
        reasons.append("sealed_key_quote_stale")
    if not evidence.quote_signature_verified:
        reasons.append("sealed_key_quote_signature_invalid")
    if not evidence.evidence_provenance:
        reasons.append("sealed_key_evidence_provenance_missing")
    if evidence.contradictions:
        reasons.extend(f"sealed_key_contradiction:{x}" for x in evidence.contradictions)

    return TPMUnsealDecision(
        unseal_eligible=not reasons,
        status="TPM_UNSEAL_ELIGIBLE_IN_SCOPE" if not reasons else "TPM_UNSEAL_DENIED",
        reasons=tuple(reasons),
        key_released=False,
        authority_granted=False,
    )
