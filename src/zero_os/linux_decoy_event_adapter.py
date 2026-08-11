from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from zero_os.decoy_event_ingest import DecoyAccessKind, DecoyKernelEvent


class LinuxEventSource(str, Enum):
    AUDITD = "auditd"
    FANOTIFY = "fanotify"
    EBPF_LSM = "ebpf_lsm"


@dataclass(frozen=True)
class LinuxAccessRecord:
    source: LinuxEventSource
    source_event_id: str
    audit_sequence: int
    beacon_id: str
    actor_id: str
    pid: int
    process_start_time_ns: int
    executable_hash: str
    uid: int
    gid: int
    action: str
    object_path: str
    observed_at: str
    peer_identity: str = ""
    source_authenticated: bool = False
    kernel_origin_verified: bool = False


@dataclass(frozen=True)
class LinuxAdapterDecision:
    accepted: bool
    status: str
    reasons: tuple[str, ...]
    event: DecoyKernelEvent | None
    authority_granted: bool = False


def adapt_linux_access_record(record: LinuxAccessRecord) -> LinuxAdapterDecision:
    reasons: list[str] = []
    if not record.source_authenticated:
        reasons.append("event_source_not_authenticated")
    if not record.kernel_origin_verified:
        reasons.append("kernel_origin_not_verified")
    if record.audit_sequence <= 0:
        reasons.append("audit_sequence_invalid")
    if record.pid <= 0 or record.process_start_time_ns <= 0:
        reasons.append("process_identity_incomplete")
    if not record.executable_hash:
        reasons.append("executable_hash_missing")
    if not record.source_event_id:
        reasons.append("source_event_id_missing")
    try:
        kind = DecoyAccessKind(record.action)
    except ValueError:
        reasons.append("unsupported_decoy_access_kind")
        kind = DecoyAccessKind.STAT
    if reasons:
        return LinuxAdapterDecision(False, "LINUX_EVENT_REJECTED", tuple(reasons), None)
    event = DecoyKernelEvent(
        beacon_id=record.beacon_id,
        actor_id=record.actor_id,
        process_id=str(record.pid),
        process_start_time_ns=record.process_start_time_ns,
        executable_hash=record.executable_hash,
        uid=record.uid,
        gid=record.gid,
        access_kind=kind,
        object_path=record.object_path,
        observed_at=record.observed_at,
        source=record.source.value,
        source_event_id=record.source_event_id,
        peer_identity=record.peer_identity,
        kernel_audit_sequence=record.audit_sequence,
        provenance_verified=True,
    )
    return LinuxAdapterDecision(True, "LINUX_KERNEL_EVENT_ACCEPTED_AS_EVIDENCE", (), event)


def linux_adapter_invariants() -> dict:
    return {
        "caller_label_alone_is_not_kernel_provenance": True,
        "kernel_origin_must_be_verified": True,
        "source_authentication_required": True,
        "adapter_grants_no_authority": True,
    }
