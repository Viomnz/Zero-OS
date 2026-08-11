from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Protocol

from zero_os.authority_root_of_trust import AuthorityAttestation
from zero_os.capability_lease import require_scope
from zero_os.containment_sink_enforcement import evaluate_sensitive_sink
from zero_os.live_containment_state import LiveContainmentRegistry
from zero_os.protected_data_authority import CompromiseState, DataOperation, verify_data_grant
from zero_os.protected_data_cipher import EncryptedProtectedData
from zero_os.protected_data_runtime import load_subject
from zero_os.protected_key_release import KeyReleaseBrokerDescriptor, KeyReleaseDecision, KeyReleaseRequest, evaluate_key_release


@dataclass(frozen=True)
class BrokerDecryptResponse:
    ok: bool
    status: str
    plaintext: bytes
    broker_id: str
    key_id: str
    data_id: str
    content_revision: str
    operation: str
    destination: str = ""


class ProtectedDataBroker(Protocol):
    descriptor: KeyReleaseBrokerDescriptor

    def decrypt(self, request: KeyReleaseRequest, container: EncryptedProtectedData) -> BrokerDecryptResponse:
        ...


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_protected_via_broker(
    cwd: str,
    *,
    principal_id: str,
    process_identity: str,
    containment: LiveContainmentRegistry,
    data_id: str,
    grant: AuthorityAttestation,
    broker: ProtectedDataBroker,
    container: EncryptedProtectedData,
    expected_containment_revision: int | None = None,
    compromise: CompromiseState | None = None,
) -> bytes:
    initial_sink = evaluate_sensitive_sink(
        containment=containment,
        process_identity=process_identity,
        operation="key_release",
        expected_revision=expected_containment_revision,
    )
    if not initial_sink.allowed:
        raise PermissionError(";".join(initial_sink.reasons) or initial_sink.status)

    capability = require_scope("protected_data:read", cwd=cwd)
    if not bool(capability.get("ok", False)):
        raise PermissionError(str(capability.get("reason", "protected_data_read_capability_missing")))

    subject, _ = load_subject(cwd, data_id)
    if container.data_id != subject.data_id or container.content_revision != subject.state_revision:
        raise PermissionError("protected_data_cipher_subject_revision_mismatch")

    compromise_state = compromise or CompromiseState()
    grant_verdict = verify_data_grant(
        cwd,
        principal_id=principal_id,
        subject=subject,
        operation=DataOperation.READ,
        attestation=grant,
        compromise=compromise_state,
    )
    grant_ok = bool(grant_verdict.get("ok", False))
    process_compromised = bool(getattr(compromise_state, "process_contested", False) or getattr(compromise_state, "principal_contested", False))

    request = KeyReleaseRequest(
        principal_id=principal_id,
        data_id=subject.data_id,
        content_revision=subject.state_revision,
        key_id=container.key_id,
        operation="read",
        destination="",
        data_grant_id=str(grant.artifact_id),
        authority_artifact_id=str(grant.artifact_id),
        process_identity=str(process_identity),
    )
    release: KeyReleaseDecision = evaluate_key_release(
        descriptor=broker.descriptor,
        request=request,
        data_grant_verified=grant_ok,
        capability_verified=bool(capability.get("ok", False)),
        process_compromised=process_compromised,
        exact_binding_verified=True,
    )
    if not release.release_eligible:
        raise PermissionError(";".join(release.reasons) or "protected_key_release_denied")

    # The broker boundary rechecks live state immediately before decrypt. A grant
    # that was valid before a decoy contradiction cannot cross this point later.
    broker_sink = evaluate_sensitive_sink(
        containment=containment,
        process_identity=process_identity,
        operation="key_release",
        expected_revision=initial_sink.containment_revision,
    )
    if not broker_sink.allowed:
        raise PermissionError(";".join(broker_sink.reasons) or broker_sink.status)

    response = broker.decrypt(request, container)
    if not response.ok:
        raise PermissionError(response.status or "protected_broker_decrypt_denied")
    if response.broker_id != broker.descriptor.broker_id:
        raise PermissionError("protected_broker_identity_mismatch")
    if response.key_id != container.key_id or response.data_id != subject.data_id or response.content_revision != subject.state_revision:
        raise PermissionError("protected_broker_response_binding_mismatch")
    if response.operation != "read" or response.destination:
        raise PermissionError("protected_broker_response_operation_mismatch")
    if _sha256(response.plaintext) != subject.state_revision:
        raise PermissionError("protected_broker_plaintext_revision_contradiction")

    final_sink = evaluate_sensitive_sink(
        containment=containment,
        process_identity=process_identity,
        operation="protected_read",
        expected_revision=broker_sink.containment_revision,
    )
    if not final_sink.allowed:
        raise PermissionError(";".join(final_sink.reasons) or final_sink.status)
    return bytes(response.plaintext)
