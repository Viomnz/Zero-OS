from zero_os.agent_permission_policy import classify_action
from zero_os.capability_lease import capability_lease_context, issue_capability_lease


def test_sensitive_executor_read_fails_closed_without_constitutional_lease(tmp_path):
    policy = classify_action(str(tmp_path), "web_fetch")
    assert policy["decision"] == "deny"
    assert policy["pure_logic_authority"]["reason"] == "constitutional_capability_lease_missing"


def test_low_risk_status_remains_available_without_lease(tmp_path):
    policy = classify_action(str(tmp_path), "system_status")
    assert policy["decision"] == "allow"


def test_sensitive_executor_read_accepts_exact_scoped_live_lease(tmp_path):
    lease = issue_capability_lease("agent-a", {"network:fetch"})
    with capability_lease_context(lease):
        policy = classify_action(str(tmp_path), "web_fetch")
    assert policy["decision"] == "allow"
    assert policy["pure_logic_authority"]["reason"] == "v5_constitutional_capability_lease_present"


def test_wrong_scope_lease_does_not_authorize_sensitive_action(tmp_path):
    lease = issue_capability_lease("agent-a", {"runtime:status"})
    with capability_lease_context(lease):
        policy = classify_action(str(tmp_path), "web_fetch")
    assert policy["decision"] == "deny"
    assert policy["pure_logic_authority"]["reason"] == "constitutional_capability_scope_missing"
