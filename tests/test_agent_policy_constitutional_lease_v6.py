from datetime import datetime, timedelta, timezone

from zero_os.agent_permission_policy import classify_action
from zero_os.authority_ledger import AuthorityLedger, AuthorityRecord
from zero_os.authority_root_of_trust import issue_attestation_from_constitution
from zero_os.capability_lease import capability_lease_context, lease_from_attestation
from zero_os.objective_authority import ObjectiveAuthority, ObjectiveAuthorityLedger
from zero_os.pure_logic_authority_kernel import ConstitutionalRequest, IdentityAuthority
from zero_os.resource_law_budget import allocate_verification_budget


def _lease(cwd: str, scopes):
    action_scope = "network:fetch"
    expires = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()
    authority = AuthorityLedger(); authority.put(AuthorityRecord("claim-a", "network-a", "capability_authority", "v", "r1", frozenset({action_scope}), "SURVIVED_IN_SCOPE", expires_at_utc=expires))
    objectives = ObjectiveAuthorityLedger(); objectives.put(ObjectiveAuthority("obj-a", "fetch", ("test",), frozenset({action_scope}), status="SURVIVED_IN_SCOPE", expires_at_utc=expires))
    request = ConstitutionalRequest(IdentityAuthority("agent-a", ("test",), True, frozenset({action_scope})), action_scope, "obj-a", "claim-a", "web_fetch", "high", True)
    attestation, _ = issue_attestation_from_constitution(cwd, artifact_kind="capability_lease", constitutional_request=request, authority_ledger=authority, objective_ledger=objectives, verification_budget=allocate_verification_budget(consequence="high", reversibility="high"), active_dependency_ids=(), subject_id="network-a", state_revision="r1", scopes=scopes)
    return lease_from_attestation(cwd, attestation)


def test_sensitive_executor_read_fails_closed_without_constitutional_lease(tmp_path):
    policy = classify_action(str(tmp_path), "web_fetch")
    assert policy["decision"] == "deny"
    assert policy["pure_logic_authority"]["reason"] == "constitutional_capability_lease_missing"


def test_low_risk_status_remains_available_without_lease(tmp_path):
    assert classify_action(str(tmp_path), "system_status")["decision"] == "allow"


def test_sensitive_executor_read_accepts_exact_scoped_live_lease(tmp_path):
    lease = _lease(str(tmp_path), ("network:fetch",))
    with capability_lease_context(lease):
        policy = classify_action(str(tmp_path), "web_fetch")
    assert policy["decision"] == "allow"
    assert policy["pure_logic_authority"]["reason"] == "v8_attested_constitutional_capability_lease_present"


def test_wrong_scope_lease_is_rejected_by_root_issuer(tmp_path):
    try:
        _lease(str(tmp_path), ("runtime:status",))
    except PermissionError as exc:
        assert "issuer scope" in str(exc)
        return
    raise AssertionError("root issuer accepted a lease that omitted the constitutional action scope")
