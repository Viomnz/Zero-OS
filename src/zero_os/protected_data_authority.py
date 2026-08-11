from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from zero_os.authority_root_of_trust import AuthorityAttestation, verify_attestation


class DataSensitivity(str, Enum):
    PUBLIC = "PUBLIC"
    INTERNAL = "INTERNAL"
    CONFIDENTIAL = "CONFIDENTIAL"
    SECRET = "SECRET"


class DataOperation(str, Enum):
    READ = "READ"
    EXPORT = "EXPORT"


@dataclass(frozen=True)
class ProtectedDataSubject:
    data_id: str
    state_revision: str
    sensitivity: DataSensitivity
    provenance: str
    allowed_destinations: tuple[str, ...] = ()
    network_export_default: bool = False


@dataclass(frozen=True)
class CompromiseState:
    principal_contested: bool = False
    process_contested: bool = False
    telemetry_contested: bool = False
    severity: int = 0
    reasons: tuple[str, ...] = ()


def _scope_for_item(data_id: str) -> str:
    return f"protected_data:item:{data_id}"


def _scope_for_destination(destination: str) -> str:
    return f"protected_data:destination:{destination}"


def verify_data_grant(
    cwd: str,
    *,
    principal_id: str,
    subject: ProtectedDataSubject,
    operation: DataOperation,
    attestation: AuthorityAttestation,
    destination: str = "",
    compromise: CompromiseState | None = None,
) -> dict:
    """Verify exact, revision-bound protected-data authority.

    This function does not mint authority. It verifies an authority artifact already
    issued by the Pure Logic authority root and checks data-specific bindings.
    """
    compromise = compromise or CompromiseState()
    verified = verify_attestation(cwd, attestation)
    if not bool(verified.get("ok", False)):
        return {"ok": False, "status": "DATA_AUTHORITY_DENIED", "reason": str(verified.get("reason", "attestation_invalid"))}
    if attestation.artifact_kind != "protected_data_grant":
        return {"ok": False, "status": "DATA_AUTHORITY_DENIED", "reason": "wrong_artifact_kind"}
    if attestation.principal_id != str(principal_id):
        return {"ok": False, "status": "DATA_AUTHORITY_DENIED", "reason": "principal_binding_mismatch"}
    if attestation.subject_id != subject.data_id:
        return {"ok": False, "status": "DATA_AUTHORITY_DENIED", "reason": "data_subject_binding_mismatch"}
    if attestation.state_revision != subject.state_revision:
        return {"ok": False, "status": "DATA_AUTHORITY_DENIED", "reason": "data_revision_binding_mismatch"}

    expected_action = "protected_data_read" if operation == DataOperation.READ else "protected_data_export"
    if attestation.action_kind != expected_action:
        return {"ok": False, "status": "DATA_AUTHORITY_DENIED", "reason": "operation_binding_mismatch"}

    scopes = set(attestation.scopes)
    required = {"protected_data:read" if operation == DataOperation.READ else "protected_data:export", _scope_for_item(subject.data_id)}
    missing = sorted(required - scopes)
    if missing:
        return {"ok": False, "status": "DATA_AUTHORITY_DENIED", "reason": "data_scope_missing", "missing_scopes": missing}

    # Compromise shrinks authority. It never broadens it.
    if compromise.principal_contested or compromise.process_contested:
        return {"ok": False, "status": "DATA_AUTHORITY_CONTESTED", "reason": "principal_or_process_contested", "compromise_reasons": list(compromise.reasons)}
    if compromise.severity >= 2 and subject.sensitivity in {DataSensitivity.CONFIDENTIAL, DataSensitivity.SECRET}:
        return {"ok": False, "status": "DATA_AUTHORITY_CONTESTED", "reason": "compromise_severity_exceeds_sensitive_data_threshold", "compromise_reasons": list(compromise.reasons)}

    if operation == DataOperation.EXPORT:
        normalized_destination = str(destination or "").strip()
        if not normalized_destination:
            return {"ok": False, "status": "DATA_AUTHORITY_DENIED", "reason": "export_destination_missing"}
        if _scope_for_destination(normalized_destination) not in scopes:
            return {"ok": False, "status": "DATA_AUTHORITY_DENIED", "reason": "destination_binding_missing"}
        if subject.allowed_destinations and normalized_destination not in set(subject.allowed_destinations):
            return {"ok": False, "status": "DATA_AUTHORITY_DENIED", "reason": "destination_not_allowed_by_data_contract"}
        if subject.sensitivity == DataSensitivity.SECRET and normalized_destination.startswith("network:") and not subject.network_export_default:
            # Secret network export needs an explicit per-destination allow in both
            # the subject contract and signed authority scopes.
            if normalized_destination not in set(subject.allowed_destinations):
                return {"ok": False, "status": "DATA_AUTHORITY_DENIED", "reason": "secret_network_export_default_deny"}

    return {
        "ok": True,
        "status": "DATA_AUTHORITY_VERIFIED_IN_SCOPE",
        "reason": "exact_revision_and_operation_bound_grant_verified",
        "data_id": subject.data_id,
        "state_revision": subject.state_revision,
        "sensitivity": subject.sensitivity.value,
        "operation": operation.value,
        "destination": str(destination or ""),
        "authority_granted_by_this_gate": False,
        "path_logic_final_authority": False,
    }


def read_grant_cannot_authorize_export(attestation: AuthorityAttestation) -> bool:
    return attestation.action_kind == "protected_data_read" and "protected_data:export" not in set(attestation.scopes)
