from zero_os.authority_integrity_audit import audit_authority_integrity
from zero_os.authority_ledger import AuthorityLedger, AuthorityRecord, PROVISIONAL, REVOKED
from zero_os.evidence_binding import canonical_fingerprint


def _record(authority_id, *, deps=(), state=PROVISIONAL, scope=("x",), subject="s", claim_type="c", revision="r"):
    return AuthorityRecord(
        authority_id=authority_id,
        subject_id=subject,
        claim_type=claim_type,
        value_fingerprint=canonical_fingerprint({"id": authority_id}),
        state_revision=revision,
        demonstrated_scope=frozenset(scope),
        state=state,
        dependencies=frozenset(deps),
    )


def test_missing_dependency_blocks_authority():
    ledger = AuthorityLedger()
    ledger.put(_record("action", deps=("missing",)))
    audit = audit_authority_integrity(ledger)
    assert audit["authority_integrity_permitted"] is False
    assert any(item["failure"] == "missing_dependency" for item in audit["findings"])


def test_active_authority_cannot_depend_on_revoked_authority():
    ledger = AuthorityLedger()
    ledger.put(_record("verifier", state=REVOKED))
    ledger.put(_record("action", deps=("verifier",)))
    audit = audit_authority_integrity(ledger)
    assert audit["authority_integrity_permitted"] is False
    assert any(item["failure"] == "active_depends_on_inactive_authority" for item in audit["findings"])


def test_dependency_cycle_is_not_self_supporting_evidence():
    ledger = AuthorityLedger()
    ledger.put(_record("a", deps=("b",)))
    ledger.put(_record("b", deps=("a",)))
    audit = audit_authority_integrity(ledger)
    assert audit["authority_integrity_permitted"] is False
    assert any(item["failure"] == "authority_dependency_cycle" for item in audit["findings"])


def test_well_formed_dependency_graph_passes_integrity():
    ledger = AuthorityLedger()
    ledger.put(_record("verifier"))
    ledger.put(_record("action", deps=("verifier",)))
    audit = audit_authority_integrity(ledger)
    assert audit["authority_integrity_permitted"] is True
