from datetime import datetime, timedelta, timezone

from zero_os.agent_permission_policy import classify_action
from zero_os.authority_ledger import AuthorityLedger, AuthorityRecord, PROVISIONAL
from zero_os.evidence_binding import EvidenceRecord, canonical_fingerprint
from zero_os.execution_authority_ticket import consume_execution_ticket, issue_execution_ticket
from zero_os.final_action_authority import ActionAuthorityRequest, authorize_and_issue_execution_ticket


def _evidence(subject, claim_type, value, revision, source, lineage, method, scope):
    return EvidenceRecord(
        evidence_id=source,
        subject_id=subject,
        claim_type=claim_type,
        value_fingerprint=canonical_fingerprint(value),
        state_revision=revision,
        source=source,
        source_lineage=frozenset(lineage),
        method_family=method,
        supports=True,
        scope=frozenset({scope}),
    )


def test_mutating_policy_fails_closed_without_ticket(tmp_path):
    decision = classify_action(str(tmp_path), "code_change")
    assert decision["decision"] == "deny"
    assert decision["pure_logic_authority"]["ok"] is False


def test_execution_ticket_is_single_use(tmp_path):
    issue_execution_ticket(
        str(tmp_path),
        action_kind="code_change",
        authority_id="auth:code",
        subject_id="repo:file.py",
        required_scope="mutation:code_change",
        state_revision="sha:1",
    )
    first = consume_execution_ticket(str(tmp_path), "code_change")
    second = consume_execution_ticket(str(tmp_path), "code_change")
    assert first["ok"] is True
    assert second["ok"] is False


def test_final_authority_can_mint_ticket_only_after_exact_independent_evidence(tmp_path):
    value = {"change": "repair", "target": "repo:file.py"}
    scope = "mutation:code_change"
    ledger = AuthorityLedger()
    ledger.put(
        AuthorityRecord(
            authority_id="auth:code",
            subject_id="repo:file.py",
            claim_type="code_mutation",
            value_fingerprint=canonical_fingerprint(value),
            state_revision="sha:1",
            demonstrated_scope=frozenset({scope}),
            state=PROVISIONAL,
            expires_at_utc=(datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat(),
        )
    )
    evidence = [
        _evidence("repo:file.py", "code_mutation", value, "sha:1", "formal", {"formal"}, "symbolic", scope),
        _evidence("repo:file.py", "code_mutation", value, "sha:1", "runtime", {"runtime"}, "execution", scope),
    ]
    request = ActionAuthorityRequest(
        action_id="change:1",
        subject_id="repo:file.py",
        claim_type="code_mutation",
        claim_value=value,
        state_revision="sha:1",
        required_scope=scope,
        authority_id="auth:code",
    )
    result = authorize_and_issue_execution_ticket(
        str(tmp_path),
        "code_change",
        request,
        ledger=ledger,
        evidence=evidence,
    )
    assert result["ok"] is True
    policy = classify_action(str(tmp_path), "code_change")
    assert policy["decision"] == "allow"
    assert policy["pure_logic_authority"]["ok"] is True
    assert classify_action(str(tmp_path), "code_change")["decision"] == "deny"


def test_wrong_state_revision_cannot_mint_ticket(tmp_path):
    value = {"change": "repair"}
    scope = "mutation:code_change"
    ledger = AuthorityLedger()
    ledger.put(
        AuthorityRecord(
            authority_id="auth:code",
            subject_id="repo:file.py",
            claim_type="code_mutation",
            value_fingerprint=canonical_fingerprint(value),
            state_revision="sha:old",
            demonstrated_scope=frozenset({scope}),
            state=PROVISIONAL,
        )
    )
    request = ActionAuthorityRequest(
        action_id="change:2",
        subject_id="repo:file.py",
        claim_type="code_mutation",
        claim_value=value,
        state_revision="sha:new",
        required_scope=scope,
        authority_id="auth:code",
    )
    result = authorize_and_issue_execution_ticket(str(tmp_path), "code_change", request, ledger=ledger, evidence=[])
    assert result["ok"] is False
    assert consume_execution_ticket(str(tmp_path), "code_change")["ok"] is False
