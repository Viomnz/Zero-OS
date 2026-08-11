from zero_os.capability_lease import capability_lease_context, issue_capability_lease
from zero_os.network_egress_policy import evaluate_egress
from zero_os.process_capability_policy import authorize_process, classify_executable


def test_network_requires_destination_binding():
    lease = issue_capability_lease("agent", {"network:fetch"})
    with capability_lease_context(lease):
        decision = evaluate_egress("https://example.com/data")
    assert decision.allowed is False
    assert decision.reason == "destination_scope_missing"


def test_network_allows_exact_destination_scope():
    lease = issue_capability_lease("agent", {"network:fetch", "host:example.com"})
    with capability_lease_context(lease):
        decision = evaluate_egress("https://example.com/data")
    assert decision.allowed is True


def test_network_credential_transmit_needs_separate_scope():
    lease = issue_capability_lease("agent", {"network:fetch", "host:api.example.com"})
    with capability_lease_context(lease):
        decision = evaluate_egress("https://api.example.com/data", headers={"Authorization": "Bearer secret"})
    assert decision.allowed is False
    assert decision.reason == "credential_transmit_scope_missing"


def test_local_network_needs_explicit_scope():
    lease = issue_capability_lease("agent", {"network:fetch", "host:127.0.0.1"})
    with capability_lease_context(lease):
        decision = evaluate_egress("http://127.0.0.1:8080/health")
    assert decision.allowed is False
    assert decision.reason == "local_network_scope_missing"


def test_process_family_is_classified_without_execution():
    assert classify_executable("git") == "process:git"
    assert classify_executable("bash") == "process:shell"
    assert classify_executable("mystery-tool") == "process:unclassified"


def test_process_scope_is_required():
    lease = issue_capability_lease("agent", {"process:test"})
    with capability_lease_context(lease):
        denied = authorize_process("git")
        allowed = authorize_process("pytest")
    assert denied.allowed is False
    assert allowed.allowed is True
