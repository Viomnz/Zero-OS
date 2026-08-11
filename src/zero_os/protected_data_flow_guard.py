from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from zero_os.authority_root_of_trust import AuthorityAttestation
from zero_os.protected_data_authority import (
    CompromiseState,
    DataOperation,
    DataSensitivity,
    ProtectedDataSubject,
    verify_data_grant,
)


class DataChannel(str, Enum):
    MEMORY = "memory"
    IPC = "ipc"
    CLIPBOARD = "clipboard"
    NETWORK = "network"
    REMOVABLE = "removable"
    LOCAL_FILE = "local_file"


_EXPORT_CHANNELS = {DataChannel.IPC, DataChannel.CLIPBOARD, DataChannel.NETWORK, DataChannel.REMOVABLE, DataChannel.LOCAL_FILE}


@dataclass(frozen=True)
class DataFlowRequest:
    principal_id: str
    subject: ProtectedDataSubject
    channel: DataChannel
    destination: str
    operation: DataOperation
    attestation: AuthorityAttestation
    compromise: CompromiseState = CompromiseState()


def authorize_data_flow(cwd: str, request: DataFlowRequest) -> dict:
    """Verify that a sensitive data transition is independently authorized.

    Reading data into a process does not imply permission to move it to another
    process, clipboard, device, file, or network destination.
    """
    if request.operation == DataOperation.READ and request.channel in _EXPORT_CHANNELS:
        return {
            "ok": False,
            "status": "DATA_FLOW_DENIED",
            "reason": "read_authority_cannot_cross_export_channel",
            "channel": request.channel.value,
        }

    if request.operation == DataOperation.EXPORT and request.channel == DataChannel.MEMORY:
        return {
            "ok": False,
            "status": "DATA_FLOW_DENIED",
            "reason": "export_requires_explicit_sink_channel",
        }

    destination = str(request.destination or "").strip()
    expected_prefix = f"{request.channel.value}:"
    if request.operation == DataOperation.EXPORT and not destination.startswith(expected_prefix):
        return {
            "ok": False,
            "status": "DATA_FLOW_DENIED",
            "reason": "destination_channel_binding_mismatch",
            "expected_prefix": expected_prefix,
        }

    verdict = verify_data_grant(
        cwd,
        principal_id=request.principal_id,
        subject=request.subject,
        operation=request.operation,
        attestation=request.attestation,
        destination=destination,
        compromise=request.compromise,
    )
    if not bool(verdict.get("ok", False)):
        return {**verdict, "channel": request.channel.value}

    if request.operation == DataOperation.EXPORT:
        if request.subject.sensitivity == DataSensitivity.SECRET and request.channel in {DataChannel.NETWORK, DataChannel.CLIPBOARD, DataChannel.REMOVABLE}:
            # Secret material only leaves through destinations explicitly named in
            # both the data contract and the signed grant. No wildcard export.
            if destination not in set(request.subject.allowed_destinations):
                return {
                    "ok": False,
                    "status": "DATA_FLOW_DENIED",
                    "reason": "secret_export_destination_not_predeclared",
                    "channel": request.channel.value,
                }

    return {
        "ok": True,
        "status": "DATA_FLOW_VERIFIED_IN_SCOPE",
        "reason": "source_operation_channel_destination_binding_survived",
        "data_id": request.subject.data_id,
        "channel": request.channel.value,
        "destination": destination,
        "operation": request.operation.value,
        "authority_granted_by_flow_guard": False,
        "path_logic_final_authority": False,
    }


def quarantine_capability_response(*, principal_id: str, reasons: tuple[str, ...]) -> dict:
    """Describe fail-closed capability shrinkage after compromise evidence.

    Actual lease revocation remains the responsibility of the authority kernel.
    This guard never mints or revokes authority by itself.
    """
    return {
        "principal_id": principal_id,
        "status": "REQUEST_AUTHORITY_SHRINK",
        "requested_effect": "revoke_sensitive_read_and_export_capabilities",
        "preserve_capabilities": ["runtime:observe", "contradiction:status"],
        "reasons": list(reasons),
        "authority_changed_by_this_guard": False,
    }
