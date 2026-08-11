from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

from zero_os.decoy_beacon import DecoyBeacon, DecoyTouch
from zero_os.process_identity_evidence import canonical_process_identity


class DecoyAccessKind(str, Enum):
    STAT = "stat"
    OPEN = "open"
    READ = "read"
    EXEC = "exec"
    LIST = "list"
    IPC_PROBE = "ipc_probe"
    CREDENTIAL_PROBE = "credential_probe"


@dataclass(frozen=True)
class DecoyKernelEvent:
    beacon_id: str
    actor_id: str
    process_id: str
    process_start_time_ns: int
    executable_hash: str
    uid: int
    gid: int
    access_kind: DecoyAccessKind
    object_path: str
    observed_at: str
    source: str
    source_event_id: str
    peer_identity: str = ""
    kernel_audit_sequence: int = 0
    provenance_verified: bool = False


@dataclass(frozen=True)
class DecoyIngestDecision:
    accepted: bool
    status: str
    reasons: tuple[str, ...]
    touch: DecoyTouch | None
    authority_granted: bool = False
    final_malicious_judgment: bool = False


def ingest_decoy_event(beacon: DecoyBeacon, event: DecoyKernelEvent) -> DecoyIngestDecision:
    reasons: list[str] = []
    if event.beacon_id != beacon.beacon_id:
        reasons.append("beacon_id_mismatch")
    if event.object_path != beacon.protected_location:
        reasons.append("decoy_location_mismatch")
    if not event.provenance_verified:
        reasons.append("kernel_event_provenance_unverified")
    if not event.source or not event.source_event_id:
        reasons.append("kernel_event_identity_missing")
    if event.kernel_audit_sequence <= 0:
        reasons.append("kernel_audit_sequence_missing")
    if event.process_start_time_ns <= 0:
        reasons.append("process_lifetime_binding_missing")
    if not event.executable_hash or ":" in str(event.executable_hash):
        reasons.append("process_executable_hash_missing")
    try:
        datetime.fromisoformat(event.observed_at.replace("Z", "+00:00"))
    except ValueError:
        reasons.append("invalid_observation_time")
    if reasons:
        return DecoyIngestDecision(False, "DECOY_EVENT_REJECTED", tuple(reasons), None)

    process_identity = canonical_process_identity(
        pid=int(event.process_id),
        process_start_time_ns=event.process_start_time_ns,
        executable_hash=event.executable_hash,
    )
    expected_identity = process_identity in set(beacon.expected_process_identities)
    touch = DecoyTouch(
        beacon_id=event.beacon_id,
        actor_id=event.actor_id,
        process_id=process_identity,
        action=event.access_kind.value,
        observed_at=event.observed_at,
        provenance=(
            f"source:{event.source}",
            f"event:{event.source_event_id}",
            f"audit_seq:{event.kernel_audit_sequence}",
            f"uid:{event.uid}",
            f"gid:{event.gid}",
            f"object:{event.object_path}",
        ),
        expected_actor=expected_identity,
        accessor_binding_verified=expected_identity,
    )
    return DecoyIngestDecision(True, "DECOY_EVENT_ACCEPTED_AS_EVIDENCE", (), touch)


def instrumentation_invariants() -> dict:
    return {
        "kernel_event_is_evidence_not_authority": True,
        "process_identity_bound_to_lifetime": True,
        "executable_hash_required": True,
        "audit_sequence_required": True,
        "caller_actor_label_cannot_suppress_decoy": True,
        "expected_accessor_requires_exact_process_identity": True,
        "touch_is_not_final_malicious_judgment": True,
        "authority_granted": False,
    }
