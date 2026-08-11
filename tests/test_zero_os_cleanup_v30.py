from zero_os.protected_data_authority import DataSensitivity, ProtectedDataSubject
from zero_os.protected_data_runtime import _direct_plaintext_allowed
from zero_os.protected_export_sinks import ExportAuthorizationEvidence


def _subject(sensitivity: DataSensitivity) -> ProtectedDataSubject:
    return ProtectedDataSubject(
        data_id="d1",
        state_revision="abc",
        sensitivity=sensitivity,
        provenance="test",
    )


def test_direct_plaintext_path_rejects_confidential_and_secret_data():
    assert not _direct_plaintext_allowed(_subject(DataSensitivity.CONFIDENTIAL))
    assert not _direct_plaintext_allowed(_subject(DataSensitivity.SECRET))


def test_direct_plaintext_path_only_allows_nonsecret_compatibility_data():
    assert _direct_plaintext_allowed(_subject(DataSensitivity.PUBLIC))
    assert _direct_plaintext_allowed(_subject(DataSensitivity.INTERNAL))


def test_export_authorization_binds_destination_and_process():
    proof = ExportAuthorizationEvidence(
        verified=True,
        status="DATA_FLOW_VERIFIED_IN_SCOPE",
        channel="network",
        destination="network:approved.example",
        process_identity="p1",
        data_id="d1",
        authority_artifact_id="grant-1",
        containment_revision=1,
        evidence_kind="protected_data_flow_verdict",
        authority_granted=False,
    )
    ok, reasons = proof.matches(
        channel="network",
        destination="network:approved.example",
        process_identity="p1",
    )
    assert ok, reasons

    ok, reasons = proof.matches(
        channel="network",
        destination="network:evil.example",
        process_identity="p1",
    )
    assert not ok
    assert "protected_export_destination_binding_mismatch" in reasons

    ok, reasons = proof.matches(
        channel="network",
        destination="network:approved.example",
        process_identity="p2",
    )
    assert not ok
    assert "protected_export_process_binding_mismatch" in reasons


def test_export_authorization_evidence_cannot_claim_final_authority():
    proof = ExportAuthorizationEvidence(
        verified=True,
        status="DATA_FLOW_VERIFIED_IN_SCOPE",
        channel="network",
        destination="network:approved.example",
        process_identity="p1",
        data_id="d1",
        authority_artifact_id="grant-1",
        containment_revision=1,
        evidence_kind="protected_data_flow_verdict",
        authority_granted=True,
    )
    ok, reasons = proof.matches(
        channel="network",
        destination="network:approved.example",
        process_identity="p1",
    )
    assert not ok
    assert "export_evidence_cannot_claim_final_authority" in reasons
