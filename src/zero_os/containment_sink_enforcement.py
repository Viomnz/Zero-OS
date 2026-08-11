from __future__ import annotations

from dataclasses import dataclass

from zero_os.live_containment_state import LiveContainmentRegistry, ProcessContainmentState


@dataclass(frozen=True)
class ContainmentSinkDecision:
    allowed: bool
    status: str
    reasons: tuple[str, ...]
    process_identity: str
    containment_revision: int
    authority_state: str
    authority_granted: bool = False
    path_logic_final_authority: bool = False


def evaluate_sensitive_sink(
    *,
    containment: LiveContainmentRegistry,
    process_identity: str,
    operation: str,
    expected_revision: int | None = None,
) -> ContainmentSinkDecision:
    """Re-read live containment state at the irreversible/sensitive sink.

    Earlier grants and capability leases cannot override a later containment
    contradiction. Missing or unverified process identity fails closed.
    """
    identity = str(process_identity or "").strip()
    if not identity:
        return ContainmentSinkDecision(False, "CONTAINMENT_SINK_DENIED", ("process_identity_missing",), identity, -1, "UNKNOWN")

    state: ProcessContainmentState | None = containment.processes.get(identity)
    if state is None:
        return ContainmentSinkDecision(False, "CONTAINMENT_SINK_DENIED", ("live_containment_state_missing",), identity, -1, "UNKNOWN")

    reasons: list[str] = []
    if not state.identity_verified:
        reasons.append("process_identity_not_kernel_bound")
    if state.authority_state == "UNVERIFIED":
        reasons.append("process_authority_unverified")
    if expected_revision is not None and int(expected_revision) != int(state.revision):
        reasons.append("containment_revision_stale")

    op = str(operation or "").strip().lower()
    if state.authority_state in {"CONTESTED", "QUARANTINED", "REVOKED"}:
        reasons.append(f"process_authority_{state.authority_state.lower()}")
    if op in {"protected_read", "key_release"} and not state.protected_key_release_allowed:
        reasons.append("protected_key_release_revoked")
    if op in {"protected_export", "network_export", "clipboard_export", "ipc_export", "removable_export"} and not state.protected_data_export_allowed:
        reasons.append("protected_data_export_revoked")
    if state.investigation_required and op in {"protected_read", "key_release", "protected_export", "network_export", "clipboard_export", "ipc_export", "removable_export"}:
        reasons.append("active_investigation_blocks_sensitive_sink")

    return ContainmentSinkDecision(
        allowed=not reasons,
        status="CONTAINMENT_SINK_ALLOWED_IN_SCOPE" if not reasons else "CONTAINMENT_SINK_DENIED",
        reasons=tuple(reasons),
        process_identity=identity,
        containment_revision=int(state.revision),
        authority_state=str(state.authority_state),
        authority_granted=False,
        path_logic_final_authority=False,
    )


def sink_enforcement_invariants() -> dict:
    return {
        "sink_rechecks_live_containment": True,
        "stale_pre_revocation_authority_cannot_override": True,
        "missing_sensitive_process_state_fails_closed": True,
        "unverified_process_identity_fails_closed": True,
        "containment_can_only_shrink_not_grant_authority": True,
        "path_logic_final_authority": False,
    }
