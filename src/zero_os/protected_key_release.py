from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class KeyReleaseTier(str, Enum):
    IN_PROCESS_DEVELOPMENT = "IN_PROCESS_DEVELOPMENT"
    SEPARATE_PROCESS = "SEPARATE_PROCESS"
    OS_PROTECTED = "OS_PROTECTED"
    HARDWARE_BACKED = "HARDWARE_BACKED"


@dataclass(frozen=True)
class KeyReleaseBrokerDescriptor:
    broker_id: str
    tier: KeyReleaseTier
    separate_process: bool
    separate_os_identity: bool
    runtime_can_read_master_keys: bool
    hardware_backed: bool = False
    kernel_mediated_ipc: bool = False

    def production_ready(self) -> bool:
        return bool(
            self.separate_process
            and self.separate_os_identity
            and not self.runtime_can_read_master_keys
            and self.kernel_mediated_ipc
            and self.tier in {KeyReleaseTier.OS_PROTECTED, KeyReleaseTier.HARDWARE_BACKED}
        )


@dataclass(frozen=True)
class KeyReleaseRequest:
    principal_id: str
    data_id: str
    content_revision: str
    key_id: str
    operation: str
    destination: str
    data_grant_id: str
    authority_artifact_id: str
    process_identity: str


@dataclass(frozen=True)
class KeyReleaseDecision:
    release_eligible: bool
    status: str
    reasons: tuple[str, ...]
    authority_granted: bool = False


def evaluate_key_release(*, descriptor: KeyReleaseBrokerDescriptor, request: KeyReleaseRequest, data_grant_verified: bool, capability_verified: bool, process_compromised: bool, exact_binding_verified: bool) -> KeyReleaseDecision:
    reasons: list[str] = []
    if not descriptor.production_ready():
        reasons.append("key_broker_not_production_isolated")
    if not data_grant_verified:
        reasons.append("protected_data_grant_not_verified")
    if not capability_verified:
        reasons.append("protected_data_capability_not_verified")
    if process_compromised:
        reasons.append("requesting_process_contested")
    if not exact_binding_verified:
        reasons.append("key_release_binding_mismatch")
    if request.operation not in {"read", "export"}:
        reasons.append("unsupported_key_release_operation")
    if request.operation == "export" and not request.destination:
        reasons.append("export_destination_missing")
    return KeyReleaseDecision(
        release_eligible=not reasons,
        status="ELIGIBLE_FOR_EXTERNAL_KEY_RELEASE" if not reasons else "KEY_RELEASE_DENIED",
        reasons=tuple(reasons),
        authority_granted=False,
    )


def development_descriptor() -> KeyReleaseBrokerDescriptor:
    return KeyReleaseBrokerDescriptor(
        broker_id="zero-os-dev-key-broker",
        tier=KeyReleaseTier.IN_PROCESS_DEVELOPMENT,
        separate_process=False,
        separate_os_identity=False,
        runtime_can_read_master_keys=True,
        hardware_backed=False,
        kernel_mediated_ipc=False,
    )
