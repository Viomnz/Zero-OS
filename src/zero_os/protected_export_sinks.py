from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping

from zero_os.containment_sink_enforcement import evaluate_sensitive_sink
from zero_os.live_containment_state import LiveContainmentRegistry


@dataclass(frozen=True)
class ExportSinkResult:
    ok: bool
    status: str
    channel: str
    destination: str
    containment_revision: int
    actuator_invoked: bool
    authority_granted: bool = False
    path_logic_final_authority: bool = False


@dataclass(frozen=True)
class ExportAuthorizationEvidence:
    verified: bool
    status: str
    channel: str
    destination: str
    process_identity: str
    data_id: str
    authority_artifact_id: str
    containment_revision: int
    evidence_kind: str
    authority_granted: bool = False

    @classmethod
    def from_verdict(cls, verdict: Mapping[str, object]) -> "ExportAuthorizationEvidence":
        return cls(
            verified=bool(verdict.get("ok", False)),
            status=str(verdict.get("status", "")),
            channel=str(verdict.get("channel", "")),
            destination=str(verdict.get("destination", "")),
            process_identity=str(verdict.get("process_identity", "")),
            data_id=str(verdict.get("data_id", "")),
            authority_artifact_id=str(verdict.get("authority_artifact_id", "")),
            containment_revision=int(verdict.get("containment_revision", 0) or 0),
            evidence_kind=str(verdict.get("authority_evidence_kind", "")),
            authority_granted=bool(verdict.get("authority_granted_by_this_gate", False)),
        )

    def matches(self, *, channel: str, destination: str, process_identity: str) -> tuple[bool, tuple[str, ...]]:
        reasons: list[str] = []
        if not self.verified or self.status != "DATA_FLOW_VERIFIED_IN_SCOPE":
            reasons.append("protected_export_authorization_not_verified")
        if self.evidence_kind != "protected_data_flow_verdict":
            reasons.append("protected_export_evidence_kind_invalid")
        if self.channel != channel:
            reasons.append("protected_export_channel_binding_mismatch")
        if self.destination != destination:
            reasons.append("protected_export_destination_binding_mismatch")
        if self.process_identity != process_identity:
            reasons.append("protected_export_process_binding_mismatch")
        if not self.data_id:
            reasons.append("protected_export_data_binding_missing")
        if not self.authority_artifact_id:
            reasons.append("protected_export_authority_artifact_missing")
        if self.containment_revision <= 0:
            reasons.append("protected_export_containment_revision_missing")
        if self.authority_granted:
            reasons.append("export_evidence_cannot_claim_final_authority")
        return (not reasons, tuple(reasons))


def execute_protected_export(
    *,
    containment: LiveContainmentRegistry,
    process_identity: str,
    channel: str,
    destination: str,
    payload: bytes,
    authorization: ExportAuthorizationEvidence,
    actuator: Callable[[str, bytes], object],
    expected_containment_revision: int | None = None,
) -> ExportSinkResult:
    """Invoke an export actuator only after bound authorization and live containment.

    A caller-supplied boolean is intentionally insufficient. The sink requires
    authorization evidence bound to the exact process, channel, destination,
    data subject and containment revision produced by the protected-data flow gate.
    """
    normalized = str(channel or "").strip().lower()
    identity = str(process_identity or "").strip()
    destination = str(destination or "")
    operation = {
        "network": "network_export",
        "clipboard": "clipboard_export",
        "ipc": "ipc_export",
        "removable": "removable_export",
        "local_file": "protected_export",
    }.get(normalized)
    if operation is None:
        return ExportSinkResult(False, "EXPORT_SINK_DENIED_UNSUPPORTED_CHANNEL", normalized, destination, -1, False)

    authorization_ok, authorization_reasons = authorization.matches(
        channel=normalized,
        destination=destination,
        process_identity=identity,
    )
    if not authorization_ok:
        return ExportSinkResult(False, "EXPORT_SINK_DENIED_AUTHORITY_INVALID", normalized, destination, authorization.containment_revision, False)

    if expected_containment_revision is not None and int(expected_containment_revision) != int(authorization.containment_revision):
        return ExportSinkResult(False, "EXPORT_SINK_DENIED_AUTHORITY_STALE", normalized, destination, authorization.containment_revision, False)

    before = evaluate_sensitive_sink(
        containment=containment,
        process_identity=identity,
        operation=operation,
        expected_revision=authorization.containment_revision,
    )
    if not before.allowed:
        return ExportSinkResult(False, "EXPORT_SINK_DENIED_CONTAINMENT", normalized, destination, before.containment_revision, False)

    final = evaluate_sensitive_sink(
        containment=containment,
        process_identity=identity,
        operation=operation,
        expected_revision=before.containment_revision,
    )
    if not final.allowed:
        return ExportSinkResult(False, "EXPORT_SINK_DENIED_CONTAINMENT_CHANGED", normalized, destination, final.containment_revision, False)

    actuator(destination, bytes(payload))
    return ExportSinkResult(True, "EXPORT_SINK_EXECUTED_IN_SCOPE", normalized, destination, final.containment_revision, True)


def export_sink_invariants() -> dict:
    return {
        "authorization_and_containment_are_separate": True,
        "boolean_authorization_is_insufficient": True,
        "authorization_bound_to_process_channel_destination": True,
        "live_containment_rechecked_before_actuator": True,
        "contested_process_cannot_invoke_export_actuator": True,
        "export_sink_cannot_mint_authority": True,
        "path_logic_final_authority": False,
    }
