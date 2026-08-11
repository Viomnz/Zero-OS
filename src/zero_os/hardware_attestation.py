from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field
from typing import Iterable


@dataclass(frozen=True)
class PcrValue:
    index: int
    digest_sha256: str


@dataclass(frozen=True)
class HardwareAttestationBundle:
    device_identity: str
    attestation_key_id: str
    nonce: str
    quoted_pcrs: tuple[PcrValue, ...]
    quoted_pcr_composite_sha256: str
    event_log_root_sha256: str
    measured_boot_root_sha256: str
    monotonic_counter: int
    signature_verified: bool
    secure_boot_enabled: bool
    measured_boot_enabled: bool
    debug_interface_enabled: bool = False
    dma_protection_enabled: bool = False
    provenance: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class HardwareAttestationPolicy:
    expected_device_identity: str
    expected_nonce: str
    allowed_attestation_keys: tuple[str, ...]
    required_pcr_indices: tuple[int, ...]
    minimum_monotonic_counter: int
    expected_measured_boot_root_sha256: str = ""
    expected_event_log_root_sha256: str = ""
    require_secure_boot: bool = True
    require_measured_boot: bool = True
    require_dma_protection: bool = False
    deny_debug_interface: bool = True


@dataclass(frozen=True)
class HardwareAttestationDecision:
    verified: bool
    status: str
    reasons: tuple[str, ...]
    demonstrated_pcr_indices: tuple[int, ...]
    authority_granted: bool = False
    path_logic_final_authority: bool = False


def _pcr_composite(rows: Iterable[PcrValue]) -> str:
    ordered = sorted(rows, key=lambda item: int(item.index))
    payload = bytearray()
    for row in ordered:
        digest = str(row.digest_sha256).lower()
        if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
            return ""
        payload.extend(bytes.fromhex(digest))
    return hashlib.sha256(bytes(payload)).hexdigest() if payload else ""


def verify_hardware_attestation(
    bundle: HardwareAttestationBundle,
    policy: HardwareAttestationPolicy,
) -> HardwareAttestationDecision:
    reasons: list[str] = []
    if not bundle.provenance:
        reasons.append("attestation_provenance_missing")
    if not bundle.signature_verified:
        reasons.append("attestation_signature_unverified")
    if bundle.device_identity != policy.expected_device_identity:
        reasons.append("device_identity_mismatch")
    if bundle.nonce != policy.expected_nonce or not bundle.nonce:
        reasons.append("nonce_mismatch_or_missing")
    if policy.allowed_attestation_keys and bundle.attestation_key_id not in set(policy.allowed_attestation_keys):
        reasons.append("attestation_key_not_allowed")
    if policy.require_secure_boot and not bundle.secure_boot_enabled:
        reasons.append("secure_boot_disabled")
    if policy.require_measured_boot and not bundle.measured_boot_enabled:
        reasons.append("measured_boot_disabled")
    if policy.require_dma_protection and not bundle.dma_protection_enabled:
        reasons.append("dma_protection_missing")
    if policy.deny_debug_interface and bundle.debug_interface_enabled:
        reasons.append("debug_interface_enabled")
    if bundle.monotonic_counter < policy.minimum_monotonic_counter:
        reasons.append("attestation_rollback_counter_below_policy")

    pcr_map = {int(row.index): row for row in bundle.quoted_pcrs}
    missing = [index for index in policy.required_pcr_indices if index not in pcr_map]
    reasons.extend(f"required_pcr_missing:{index}" for index in missing)
    for index, row in pcr_map.items():
        digest = str(row.digest_sha256).lower()
        if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
            reasons.append(f"pcr_digest_invalid:{index}")

    actual_composite = _pcr_composite(bundle.quoted_pcrs)
    if not actual_composite or actual_composite != str(bundle.quoted_pcr_composite_sha256).lower():
        reasons.append("quoted_pcr_composite_mismatch")
    if policy.expected_measured_boot_root_sha256 and str(bundle.measured_boot_root_sha256).lower() != policy.expected_measured_boot_root_sha256.lower():
        reasons.append("measured_boot_root_mismatch")
    if policy.expected_event_log_root_sha256 and str(bundle.event_log_root_sha256).lower() != policy.expected_event_log_root_sha256.lower():
        reasons.append("event_log_root_mismatch")

    return HardwareAttestationDecision(
        verified=not reasons,
        status="HARDWARE_ATTESTATION_VERIFIED_IN_SCOPE" if not reasons else "HARDWARE_ATTESTATION_CONTESTED",
        reasons=tuple(reasons),
        demonstrated_pcr_indices=tuple(sorted(pcr_map)),
        authority_granted=False,
        path_logic_final_authority=False,
    )


def attestation_to_dict(decision: HardwareAttestationDecision) -> dict:
    return asdict(decision)
