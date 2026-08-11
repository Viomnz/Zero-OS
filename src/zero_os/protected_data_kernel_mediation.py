from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class MediationState(str, Enum):
    UNVERIFIED = "UNVERIFIED"
    SOFTWARE_ONLY = "SOFTWARE_ONLY"
    KERNEL_MEDIATED = "KERNEL_MEDIATED"
    HARDWARE_ANCHORED = "HARDWARE_ANCHORED"
    CONTESTED = "CONTESTED"


@dataclass(frozen=True)
class KernelMediationEvidence:
    state: MediationState
    protected_store_not_readable_by_runtime_uid: bool
    plaintext_path_absent: bool
    broker_ipc_identity_enforced: bool
    ptrace_or_process_memory_escape_blocked: bool
    removable_media_sink_mediated: bool
    network_sink_mediated: bool
    clipboard_sink_mediated: bool
    ipc_sink_mediated: bool
    same_privilege_bypass_tests_passed: bool
    evidence_provenance: tuple[str, ...]
    contradictions: tuple[str, ...] = ()


@dataclass(frozen=True)
class KernelMediationDecision:
    containment_demonstrated: bool
    status: str
    reasons: tuple[str, ...]
    authority_granted: bool = False


def evaluate_kernel_mediation(evidence: KernelMediationEvidence) -> KernelMediationDecision:
    reasons: list[str] = []
    if evidence.state not in {MediationState.KERNEL_MEDIATED, MediationState.HARDWARE_ANCHORED}:
        reasons.append("filesystem_mediation_not_kernel_enforced")
    required = {
        "protected_store_runtime_uid_isolated": evidence.protected_store_not_readable_by_runtime_uid,
        "plaintext_path_absent": evidence.plaintext_path_absent,
        "broker_ipc_identity_not_enforced": evidence.broker_ipc_identity_enforced,
        "process_memory_escape_not_blocked": evidence.ptrace_or_process_memory_escape_blocked,
        "removable_media_not_mediated": evidence.removable_media_sink_mediated,
        "network_not_mediated": evidence.network_sink_mediated,
        "clipboard_not_mediated": evidence.clipboard_sink_mediated,
        "ipc_not_mediated": evidence.ipc_sink_mediated,
        "same_privilege_bypass_tests_missing": evidence.same_privilege_bypass_tests_passed,
    }
    for reason, ok in required.items():
        if not ok:
            reasons.append(reason)
    if not evidence.evidence_provenance:
        reasons.append("kernel_mediation_provenance_missing")
    if evidence.contradictions:
        reasons.extend(f"kernel_mediation_contradiction:{x}" for x in evidence.contradictions)
    return KernelMediationDecision(
        containment_demonstrated=not reasons,
        status="BREACH_CONTAINMENT_DEMONSTRATED_IN_SCOPE" if not reasons else "BREACH_CONTAINMENT_NOT_DEMONSTRATED",
        reasons=tuple(reasons),
        authority_granted=False,
    )
