from __future__ import annotations

import hashlib
import json
from pathlib import Path

from zero_os.authority_root_of_trust import AuthorityAttestation
from zero_os.capability_lease import require_scope
from zero_os.containment_sink_enforcement import evaluate_sensitive_sink
from zero_os.live_containment_state import LiveContainmentRegistry
from zero_os.protected_data_authority import (
    CompromiseState,
    DataOperation,
    DataSensitivity,
    ProtectedDataSubject,
    verify_data_grant,
)
from zero_os.protected_data_flow_guard import DataChannel, DataFlowRequest, authorize_data_flow


# Confidential and secret plaintext must be released through the isolated broker.
# This direct reader remains only for non-secret compatibility data.
DIRECT_PLAINTEXT_MAX_SENSITIVITY = DataSensitivity.INTERNAL


def _vault_root(cwd: str, *, create: bool = False) -> Path:
    root = Path(cwd).resolve() / ".zero_os" / "protected_data"
    if create:
        root.mkdir(parents=True, exist_ok=True)
    return root


def _manifest_path(cwd: str) -> Path:
    return _vault_root(cwd) / "manifest.json"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_subject(cwd: str, data_id: str) -> tuple[ProtectedDataSubject, Path]:
    manifest_path = _manifest_path(cwd)
    if not manifest_path.exists():
        raise PermissionError("protected_data_manifest_missing")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PermissionError("protected_data_manifest_invalid") from exc
    record = dict((manifest.get("items") or {}).get(str(data_id)) or {})
    if not record:
        raise PermissionError("protected_data_subject_unknown")
    relative = Path(str(record.get("relative_path") or ""))
    if not str(relative) or relative.is_absolute() or ".." in relative.parts:
        raise PermissionError("protected_data_path_invalid")
    vault = _vault_root(cwd).resolve()
    path = (vault / relative).resolve()
    if vault not in path.parents:
        raise PermissionError("protected_data_path_escaped_vault")
    try:
        sensitivity = DataSensitivity(str(record.get("sensitivity") or "SECRET"))
    except ValueError as exc:
        raise PermissionError("protected_data_sensitivity_invalid") from exc
    subject = ProtectedDataSubject(
        data_id=str(data_id),
        state_revision=str(record.get("state_revision") or ""),
        sensitivity=sensitivity,
        provenance=str(record.get("provenance") or "protected_data_manifest"),
        allowed_destinations=tuple(str(x) for x in (record.get("allowed_destinations") or [])),
        network_export_default=bool(record.get("network_export_default", False)),
    )
    if not subject.state_revision:
        raise PermissionError("protected_data_revision_missing")
    return subject, path


def _direct_plaintext_allowed(subject: ProtectedDataSubject) -> bool:
    return subject.sensitivity in {DataSensitivity.PUBLIC, DIRECT_PLAINTEXT_MAX_SENSITIVITY}


def read_protected_bytes(
    cwd: str,
    *,
    principal_id: str,
    process_identity: str,
    containment: LiveContainmentRegistry,
    data_id: str,
    grant: AuthorityAttestation,
    expected_containment_revision: int | None = None,
    compromise: CompromiseState | None = None,
) -> bytes:
    """Compatibility reader for PUBLIC/INTERNAL data only.

    CONFIDENTIAL and SECRET data must use read_protected_via_broker(), where
    ciphertext and isolated key release remain unavoidable parts of the path.
    """
    sink = evaluate_sensitive_sink(
        containment=containment,
        process_identity=process_identity,
        operation="protected_read",
        expected_revision=expected_containment_revision,
    )
    if not sink.allowed:
        raise PermissionError(";".join(sink.reasons) or sink.status)

    lease = require_scope("protected_data:read", cwd=cwd)
    if not bool(lease.get("ok", False)):
        raise PermissionError(str(lease.get("reason", "protected_data_read_capability_missing")))
    subject, path = load_subject(cwd, data_id)
    if not _direct_plaintext_allowed(subject):
        raise PermissionError("sensitive_plaintext_read_requires_isolated_broker")
    if not path.exists() or not path.is_file():
        raise PermissionError("protected_data_file_missing")
    payload = path.read_bytes()
    actual_revision = _sha256(payload)
    if actual_revision != subject.state_revision:
        raise PermissionError("protected_data_revision_contradiction")
    verdict = verify_data_grant(
        cwd,
        principal_id=principal_id,
        subject=subject,
        operation=DataOperation.READ,
        attestation=grant,
        compromise=compromise or CompromiseState(),
    )
    if not bool(verdict.get("ok", False)):
        raise PermissionError(str(verdict.get("reason", "protected_data_grant_denied")))

    final_sink = evaluate_sensitive_sink(
        containment=containment,
        process_identity=process_identity,
        operation="protected_read",
        expected_revision=sink.containment_revision,
    )
    if not final_sink.allowed:
        raise PermissionError(";".join(final_sink.reasons) or final_sink.status)
    return payload


def authorize_protected_export(
    cwd: str,
    *,
    principal_id: str,
    process_identity: str,
    containment: LiveContainmentRegistry,
    data_id: str,
    destination: str,
    channel: DataChannel,
    grant: AuthorityAttestation,
    expected_containment_revision: int | None = None,
    compromise: CompromiseState | None = None,
) -> dict:
    sink = evaluate_sensitive_sink(
        containment=containment,
        process_identity=process_identity,
        operation=f"{channel.value}_export" if channel != DataChannel.LOCAL_FILE else "protected_export",
        expected_revision=expected_containment_revision,
    )
    if not sink.allowed:
        return {"ok": False, "status": "DATA_FLOW_DENIED", "reason": ";".join(sink.reasons) or sink.status}

    lease = require_scope("protected_data:export", cwd=cwd)
    if not bool(lease.get("ok", False)):
        return {"ok": False, "status": "DATA_FLOW_DENIED", "reason": str(lease.get("reason", "protected_data_export_capability_missing"))}
    subject, path = load_subject(cwd, data_id)
    if not path.exists() or _sha256(path.read_bytes()) != subject.state_revision:
        return {"ok": False, "status": "DATA_FLOW_DENIED", "reason": "protected_data_revision_contradiction"}
    verdict = authorize_data_flow(
        cwd,
        DataFlowRequest(
            principal_id=principal_id,
            subject=subject,
            channel=channel,
            destination=destination,
            operation=DataOperation.EXPORT,
            attestation=grant,
            compromise=compromise or CompromiseState(),
        ),
    )
    if not bool(verdict.get("ok", False)):
        return verdict

    final_sink = evaluate_sensitive_sink(
        containment=containment,
        process_identity=process_identity,
        operation=f"{channel.value}_export" if channel != DataChannel.LOCAL_FILE else "protected_export",
        expected_revision=sink.containment_revision,
    )
    if not final_sink.allowed:
        return {"ok": False, "status": "DATA_FLOW_DENIED", "reason": ";".join(final_sink.reasons) or final_sink.status}
    return {
        **verdict,
        "containment_revision": final_sink.containment_revision,
        "process_identity": str(process_identity),
        "authority_artifact_id": str(grant.artifact_id),
        "authority_evidence_kind": "protected_data_flow_verdict",
        "authority_granted_by_this_gate": False,
    }
