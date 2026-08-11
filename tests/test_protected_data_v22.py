from dataclasses import replace

from zero_os.authority_root_of_trust import AuthorityAttestation
from zero_os.protected_data_authority import (
    CompromiseState,
    DataOperation,
    DataSensitivity,
    ProtectedDataSubject,
    verify_data_grant,
)
from zero_os.protected_data_flow_guard import DataChannel, DataFlowRequest, authorize_data_flow


def _attestation(*, action="protected_data_read", scopes=("protected_data:read", "protected_data:item:tax"), subject="tax", revision="r1", principal="p1"):
    return AuthorityAttestation(
        schema_version=2,
        issuer_id="zero-os-authority-root-v12-ed25519",
        artifact_kind="protected_data_grant",
        artifact_id="a1",
        principal_id=principal,
        authority_id="auth1",
        objective_id="obj1",
        action_kind=action,
        subject_id=subject,
        state_revision=revision,
        scopes=tuple(scopes),
        issued_at_utc="2026-08-10T00:00:00+00:00",
        expires_at_utc="2099-08-10T00:00:00+00:00",
        nonce="n",
        constitutional_status="PROVISIONAL_SCOPED_AUTHORITY",
        signature="sig",
    )


def _subject():
    return ProtectedDataSubject(
        data_id="tax",
        state_revision="r1",
        sensitivity=DataSensitivity.SECRET,
        provenance="test",
        allowed_destinations=("network:irs.gov",),
        network_export_default=False,
    )


def test_read_grant_does_not_authorize_export(monkeypatch):
    monkeypatch.setattr("zero_os.protected_data_authority.verify_attestation", lambda *a, **k: {"ok": True})
    verdict = verify_data_grant(
        ".",
        principal_id="p1",
        subject=_subject(),
        operation=DataOperation.EXPORT,
        attestation=_attestation(),
        destination="network:irs.gov",
    )
    assert verdict["ok"] is False
    assert verdict["reason"] == "operation_binding_mismatch"


def test_export_is_bound_to_exact_destination(monkeypatch):
    monkeypatch.setattr("zero_os.protected_data_authority.verify_attestation", lambda *a, **k: {"ok": True})
    grant = _attestation(
        action="protected_data_export",
        scopes=("protected_data:export", "protected_data:item:tax", "protected_data:destination:network:irs.gov"),
    )
    good = verify_data_grant(
        ".",
        principal_id="p1",
        subject=_subject(),
        operation=DataOperation.EXPORT,
        attestation=grant,
        destination="network:irs.gov",
    )
    bad = verify_data_grant(
        ".",
        principal_id="p1",
        subject=_subject(),
        operation=DataOperation.EXPORT,
        attestation=grant,
        destination="network:evil.example",
    )
    assert good["ok"] is True
    assert bad["ok"] is False


def test_revision_change_revokes_old_data_grant(monkeypatch):
    monkeypatch.setattr("zero_os.protected_data_authority.verify_attestation", lambda *a, **k: {"ok": True})
    changed = replace(_subject(), state_revision="r2")
    verdict = verify_data_grant(
        ".",
        principal_id="p1",
        subject=changed,
        operation=DataOperation.READ,
        attestation=_attestation(),
    )
    assert verdict["ok"] is False
    assert verdict["reason"] == "data_revision_binding_mismatch"


def test_compromise_shrinks_sensitive_authority(monkeypatch):
    monkeypatch.setattr("zero_os.protected_data_authority.verify_attestation", lambda *a, **k: {"ok": True})
    verdict = verify_data_grant(
        ".",
        principal_id="p1",
        subject=_subject(),
        operation=DataOperation.READ,
        attestation=_attestation(),
        compromise=CompromiseState(process_contested=True, severity=3, reasons=("unexpected_network_behavior",)),
    )
    assert verdict["ok"] is False
    assert verdict["status"] == "DATA_AUTHORITY_CONTESTED"


def test_read_authority_cannot_cross_network_channel(monkeypatch):
    monkeypatch.setattr("zero_os.protected_data_flow_guard.verify_data_grant", lambda *a, **k: {"ok": True})
    verdict = authorize_data_flow(
        ".",
        DataFlowRequest(
            principal_id="p1",
            subject=_subject(),
            channel=DataChannel.NETWORK,
            destination="network:irs.gov",
            operation=DataOperation.READ,
            attestation=_attestation(),
        ),
    )
    assert verdict["ok"] is False
    assert verdict["reason"] == "read_authority_cannot_cross_export_channel"


def test_secret_export_requires_predeclared_destination(monkeypatch):
    monkeypatch.setattr("zero_os.protected_data_flow_guard.verify_data_grant", lambda *a, **k: {"ok": True})
    request = DataFlowRequest(
        principal_id="p1",
        subject=_subject(),
        channel=DataChannel.NETWORK,
        destination="network:evil.example",
        operation=DataOperation.EXPORT,
        attestation=_attestation(action="protected_data_export", scopes=("protected_data:export",)),
    )
    verdict = authorize_data_flow(".", request)
    assert verdict["ok"] is False
    assert verdict["reason"] == "secret_export_destination_not_predeclared"
