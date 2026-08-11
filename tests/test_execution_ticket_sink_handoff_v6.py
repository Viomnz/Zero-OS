from datetime import datetime, timedelta, timezone

from zero_os.authority_ledger import AuthorityLedger, AuthorityRecord
from zero_os.authority_root_of_trust import issue_attestation_from_constitution
from zero_os.execution_authority_ticket import acknowledge_consumed_execution_ticket, consume_execution_ticket, ticket_from_attestation
from zero_os.objective_authority import ObjectiveAuthority, ObjectiveAuthorityLedger
from zero_os.pure_logic_authority_kernel import ConstitutionalRequest, IdentityAuthority
from zero_os.resource_law_budget import allocate_verification_budget
from zero_os.self_repair import self_repair_run


def _mint(cwd: str):
    scope = "runtime:self_repair"
    expires = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()
    authority = AuthorityLedger(); authority.put(AuthorityRecord("a1", "repair-1", "action_authority", "v", "r1", frozenset({scope}), "SURVIVED_IN_SCOPE", expires_at_utc=expires))
    objectives = ObjectiveAuthorityLedger(); objectives.put(ObjectiveAuthority("obj1", "repair", ("test",), frozenset({scope}), status="SURVIVED_IN_SCOPE", expires_at_utc=expires))
    request = ConstitutionalRequest(IdentityAuthority("operator", ("test",), True, frozenset({scope})), scope, "obj1", "a1", "self_repair", "high", True)
    attestation, _ = issue_attestation_from_constitution(cwd, artifact_kind="execution_ticket", constitutional_request=request, authority_ledger=authority, objective_ledger=objectives, verification_budget=allocate_verification_budget(consequence="high", reversibility="high"), active_dependency_ids=(), subject_id="repair-1", state_revision="r1", scopes=(scope,))
    return ticket_from_attestation(cwd, attestation)


def test_sink_handoff_requires_prior_runtime_consumption(tmp_path):
    _mint(str(tmp_path))
    ack = acknowledge_consumed_execution_ticket(str(tmp_path), "self_repair")
    assert ack["ok"] is False
    assert ack["reason"] == "fresh_consumed_ticket_handoff_missing"


def test_sink_handoff_is_single_use(tmp_path):
    _mint(str(tmp_path))
    assert consume_execution_ticket(str(tmp_path), "self_repair")["ok"] is True
    assert acknowledge_consumed_execution_ticket(str(tmp_path), "self_repair")["ok"] is True
    assert acknowledge_consumed_execution_ticket(str(tmp_path), "self_repair")["ok"] is False


def test_background_self_repair_cannot_bypass_runtime_authority(tmp_path):
    result = self_repair_run(str(tmp_path))
    assert result["ok"] is False
    assert result["blocked"] is True
    assert result["reason"] == "constitutional_self_repair_handoff_missing"
