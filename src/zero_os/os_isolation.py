from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class IsolationState(str, Enum):
    UNVERIFIED = "UNVERIFIED"
    SOFTWARE_DECLARED = "SOFTWARE_DECLARED"
    OS_ENFORCED = "OS_ENFORCED"
    HARDWARE_ANCHORED = "HARDWARE_ANCHORED"
    CONTESTED = "CONTESTED"


@dataclass(frozen=True)
class OSIsolationEvidence:
    state: IsolationState
    runtime_uid: str
    broker_uid: str
    distinct_uids: bool
    protected_store_owner_is_broker: bool
    protected_store_mode_blocks_runtime: bool
    broker_socket_peer_credentials_verified: bool
    broker_service_no_new_privileges: bool
    broker_private_tmp: bool
    broker_protect_system_strict: bool
    broker_protect_home: bool
    runtime_ptrace_broker_blocked: bool
    broker_memory_dump_blocked: bool
    runtime_namespace_cannot_mount_protected_store: bool
    runtime_cannot_open_cipher_key_store: bool
    network_egress_default_deny_for_broker: bool
    evidence_provenance: tuple[str, ...]
    contradictions: tuple[str, ...] = ()


@dataclass(frozen=True)
class OSIsolationDecision:
    isolated: bool
    status: str
    reasons: tuple[str, ...]
    authority_granted: bool = False


def evaluate_os_isolation(evidence: OSIsolationEvidence) -> OSIsolationDecision:
    reasons: list[str] = []
    if evidence.state not in {IsolationState.OS_ENFORCED, IsolationState.HARDWARE_ANCHORED}:
        reasons.append("os_isolation_not_enforced")
    if not evidence.runtime_uid or not evidence.broker_uid:
        reasons.append("runtime_or_broker_identity_missing")
    if not evidence.distinct_uids or evidence.runtime_uid == evidence.broker_uid:
        reasons.append("runtime_and_broker_share_os_identity")

    required = {
        "protected_store_owner_not_broker": evidence.protected_store_owner_is_broker,
        "protected_store_runtime_read_not_blocked": evidence.protected_store_mode_blocks_runtime,
        "broker_socket_peer_credentials_not_verified": evidence.broker_socket_peer_credentials_verified,
        "broker_no_new_privileges_missing": evidence.broker_service_no_new_privileges,
        "broker_private_tmp_missing": evidence.broker_private_tmp,
        "broker_protect_system_not_strict": evidence.broker_protect_system_strict,
        "broker_home_not_protected": evidence.broker_protect_home,
        "runtime_ptrace_escape_not_blocked": evidence.runtime_ptrace_broker_blocked,
        "broker_memory_dump_not_blocked": evidence.broker_memory_dump_blocked,
        "runtime_namespace_mount_escape_not_blocked": evidence.runtime_namespace_cannot_mount_protected_store,
        "runtime_can_open_cipher_key_store": evidence.runtime_cannot_open_cipher_key_store,
        "broker_network_egress_not_default_deny": evidence.network_egress_default_deny_for_broker,
    }
    for reason, ok in required.items():
        if not ok:
            reasons.append(reason)

    if not evidence.evidence_provenance:
        reasons.append("os_isolation_evidence_provenance_missing")
    if evidence.contradictions:
        reasons.extend(f"os_isolation_contradiction:{x}" for x in evidence.contradictions)

    return OSIsolationDecision(
        isolated=not reasons,
        status="OS_ISOLATION_DEMONSTRATED_IN_SCOPE" if not reasons else "OS_ISOLATION_NOT_DEMONSTRATED",
        reasons=tuple(reasons),
        authority_granted=False,
    )
