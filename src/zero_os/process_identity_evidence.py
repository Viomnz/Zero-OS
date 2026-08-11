from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class KernelProcessIdentityEvidence:
    """Software contract for kernel-observed process identity evidence.

    This structure is evidence, not authority. Production promotion still requires
    a real authenticated kernel/OS source to supply these fields.
    """

    pid: int
    process_start_time_ns: int
    executable_hash: str
    uid: int
    gid: int
    source: str
    source_event_id: str
    source_authenticated: bool = False
    kernel_origin_verified: bool = False


@dataclass(frozen=True)
class ProcessIdentityVerification:
    accepted: bool
    status: str
    reasons: tuple[str, ...]
    process_identity: str
    provenance: tuple[str, ...]
    authority_granted: bool = False


def canonical_process_identity(*, pid: int, process_start_time_ns: int, executable_hash: str) -> str:
    executable = str(executable_hash or "").strip().lower()
    return f"{int(pid)}:{int(process_start_time_ns)}:{executable}"


def verify_kernel_process_identity(evidence: KernelProcessIdentityEvidence) -> ProcessIdentityVerification:
    reasons: list[str] = []
    executable = str(evidence.executable_hash or "").strip().lower()
    source = str(evidence.source or "").strip()
    event_id = str(evidence.source_event_id or "").strip()

    if int(evidence.pid) <= 0:
        reasons.append("process_pid_invalid")
    if int(evidence.process_start_time_ns) <= 0:
        reasons.append("process_start_time_missing")
    if not executable or ":" in executable:
        reasons.append("process_executable_hash_invalid")
    if int(evidence.uid) < 0 or int(evidence.gid) < 0:
        reasons.append("process_os_identity_invalid")
    if not source or not event_id:
        reasons.append("process_identity_source_missing")
    if not evidence.source_authenticated:
        reasons.append("process_identity_source_not_authenticated")
    if not evidence.kernel_origin_verified:
        reasons.append("process_identity_kernel_origin_unverified")

    identity = ""
    if not reasons:
        identity = canonical_process_identity(
            pid=evidence.pid,
            process_start_time_ns=evidence.process_start_time_ns,
            executable_hash=executable,
        )

    provenance = (
        f"source:{source}",
        f"event:{event_id}",
        f"uid:{int(evidence.uid)}",
        f"gid:{int(evidence.gid)}",
    ) if not reasons else ()

    return ProcessIdentityVerification(
        accepted=not reasons,
        status="PROCESS_IDENTITY_VERIFIED_AS_EVIDENCE" if not reasons else "PROCESS_IDENTITY_REJECTED",
        reasons=tuple(reasons),
        process_identity=identity,
        provenance=provenance,
        authority_granted=False,
    )


def process_identity_invariants() -> dict:
    return {
        "pid_alone_is_not_process_identity": True,
        "process_lifetime_binding_required": True,
        "executable_hash_binding_required": True,
        "caller_label_cannot_establish_process_identity": True,
        "kernel_identity_evidence_grants_no_authority": True,
        "production_requires_real_kernel_source": True,
    }
