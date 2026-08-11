from zero_os.agent_permission_policy import classify_action
from zero_os.authority_root_of_trust import issue_attestation
from zero_os.capability_lease import capability_lease_context, lease_from_attestation


def _lease(cwd: str, scopes):
    attestation = issue_attestation(
        cwd,
        artifact_kind="capability_lease",
        principal_id="agent-a",
        authority_id="claim-a",
        objective_id="obj-a",
        action_kind="web_fetch",
        subject_id="network-a",
        state_revision="r1",
        scopes=scopes,
        constitutional_allowed=True,
        constitutional_status="AUTHORIZED",
    )
    return lease_from_attestation(cwd, attestation)


def test_sensitive_executor_read_fails_closed_without_constitutional_lease(tmp_path):
    policy = classify_action(str(tmp_path), "web_fetch")
    assert policy["decision"] == "deny"
    assert policy["pure_logic_authority"]["reason"] == "constitutional_capability_lease_missing"


def test_low_risk_status_remains_available_without_lease(tmp_path):
    policy = classify_action(str(tmp_path), "system_status")
    assert policy["decision"] == "allow"


def test_sensitive_executor_read_accepts_exact_scoped_live_lease(tmp_path):
    lease = _lease(str(tmp_path), ("network:fetch",))
    with capability_lease_context(lease):
        policy = classify_action(str(tmp_path), "web_fetch")
    assert policy["decision"] == "allow"
    assert policy["pure_logic_authority"]["reason"] == "v8_attested_constitutional_capability_lease_present"


def test_wrong_scope_lease_does_not_authorize_sensitive_action(tmp_path):
    lease = _lease(str(tmp_path), ("runtime:status",))
    with capability_lease_context(lease):
        policy = classify_action(str(tmp_path), "web_fetch")
    assert policy["decision"] == "deny"
    assert policy["pure_logic_authority"]["reason"] == "constitutional_capability_scope_missing"
