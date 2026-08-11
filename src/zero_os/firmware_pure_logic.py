from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Iterable


class FirmwareDecisionState(str, Enum):
    ALLOW_BOOT = "ALLOW_BOOT"
    SAFE_MODE = "SAFE_MODE"
    RECOVERY_REQUIRED = "RECOVERY_REQUIRED"
    CONTESTED = "CONTESTED"
    DENY = "DENY"


@dataclass(frozen=True)
class FirmwareMeasurement:
    component_id: str
    digest_sha256: str
    source: str
    measured_at_utc: str
    version: str = ""
    signer_id: str = ""
    expected_digest_sha256: str = ""
    signature_verified: bool = False
    provenance_verified: bool = False


@dataclass(frozen=True)
class HardwareTrustEvidence:
    device_identity: str
    hardware_root_present: bool
    secure_boot_enabled: bool
    measured_boot_supported: bool
    monotonic_counter: int
    debug_interface_enabled: bool = False
    dma_protection_enabled: bool = False
    provenance: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class FirmwarePolicy:
    required_components: tuple[str, ...]
    minimum_monotonic_counter: int
    allowed_signers: tuple[str, ...]
    require_hardware_root: bool = True
    require_secure_boot: bool = True
    require_measured_boot: bool = True
    require_dma_protection: bool = False
    deny_debug_interface: bool = True


@dataclass(frozen=True)
class FirmwareDecision:
    allowed: bool
    state: FirmwareDecisionState
    reasons: tuple[str, ...]
    demonstrated_scope: tuple[str, ...]
    measurements: tuple[FirmwareMeasurement, ...]
    path_logic_final_authority: bool = False
    firmware_self_certification_permitted: bool = False


def _valid_measurement(m: FirmwareMeasurement, policy: FirmwarePolicy) -> tuple[bool, str]:
    if not m.component_id:
        return False, "measurement_component_missing"
    if not m.digest_sha256:
        return False, f"measurement_digest_missing:{m.component_id}"
    if m.expected_digest_sha256 and m.digest_sha256.lower() != m.expected_digest_sha256.lower():
        return False, f"measurement_digest_mismatch:{m.component_id}"
    if not m.provenance_verified:
        return False, f"measurement_provenance_unverified:{m.component_id}"
    if not m.signature_verified:
        return False, f"measurement_signature_unverified:{m.component_id}"
    if policy.allowed_signers and m.signer_id not in set(policy.allowed_signers):
        return False, f"measurement_signer_not_allowed:{m.component_id}"
    return True, "ok"


def evaluate_firmware_boot(
    *,
    policy: FirmwarePolicy,
    hardware: HardwareTrustEvidence,
    measurements: Iterable[FirmwareMeasurement],
    active_contradictions: Iterable[str] = (),
) -> FirmwareDecision:
    rows = tuple(measurements)
    reasons: list[str] = []

    if not hardware.device_identity:
        reasons.append("hardware_identity_missing")
    if not hardware.provenance:
        reasons.append("hardware_provenance_missing")
    if policy.require_hardware_root and not hardware.hardware_root_present:
        reasons.append("hardware_root_missing")
    if policy.require_secure_boot and not hardware.secure_boot_enabled:
        reasons.append("secure_boot_disabled")
    if policy.require_measured_boot and not hardware.measured_boot_supported:
        reasons.append("measured_boot_unavailable")
    if policy.require_dma_protection and not hardware.dma_protection_enabled:
        reasons.append("dma_protection_missing")
    if policy.deny_debug_interface and hardware.debug_interface_enabled:
        reasons.append("debug_interface_enabled")
    if hardware.monotonic_counter < policy.minimum_monotonic_counter:
        reasons.append("rollback_counter_below_policy")

    by_component = {row.component_id: row for row in rows}
    missing = [component for component in policy.required_components if component not in by_component]
    reasons.extend(f"required_measurement_missing:{component}" for component in missing)

    for component in policy.required_components:
        row = by_component.get(component)
        if row is None:
            continue
        ok, reason = _valid_measurement(row, policy)
        if not ok:
            reasons.append(reason)

    contradictions = tuple(str(item) for item in active_contradictions if str(item))
    if contradictions:
        reasons.append("firmware_contradiction_active")

    if any(reason.startswith("measurement_digest_mismatch") or reason == "rollback_counter_below_policy" for reason in reasons):
        state = FirmwareDecisionState.RECOVERY_REQUIRED
    elif reasons:
        state = FirmwareDecisionState.CONTESTED
    else:
        state = FirmwareDecisionState.ALLOW_BOOT

    return FirmwareDecision(
        allowed=not reasons,
        state=state,
        reasons=tuple(reasons),
        demonstrated_scope=tuple(sorted(by_component.keys())),
        measurements=rows,
        path_logic_final_authority=False,
        firmware_self_certification_permitted=False,
    )


def firmware_invariants() -> tuple[str, ...]:
    return (
        "measurement_is_evidence_not_truth",
        "boot_permission_is_separate_from_measurement",
        "firmware_private_keys_are_not_available_to_normal_runtime",
        "rollback_requires_monotonic_or_equivalent protected state",
        "recovery_is_separate_from ordinary runtime authority",
        "path_logic_never_grants_boot_or_firmware_authority",
        "firmware_is_protected_but_revision_capable",
        "firmware_cannot certify its own correctness",
    )


def decision_to_dict(decision: FirmwareDecision) -> dict:
    payload = asdict(decision)
    payload["state"] = decision.state.value
    return payload
