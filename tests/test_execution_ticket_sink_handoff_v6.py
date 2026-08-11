from zero_os.authority_root_of_trust import issue_attestation
from zero_os.execution_authority_ticket import (
    acknowledge_consumed_execution_ticket,
    consume_execution_ticket,
    ticket_from_attestation,
)
from zero_os.self_repair import self_repair_run


def _mint(cwd: str):
    attestation = issue_attestation(
        cwd,
        artifact_kind="execution_ticket",
        principal_id="operator",
        authority_id="a1",
        objective_id="obj1",
        action_kind="self_repair",
        subject_id="repair-1",
        state_revision="r1",
        scopes=("runtime:self_repair",),
        constitutional_allowed=True,
        constitutional_status="AUTHORIZED",
    )
    return ticket_from_attestation(cwd, attestation)


def test_sink_handoff_requires_prior_runtime_consumption(tmp_path):
    _mint(str(tmp_path))
    ack = acknowledge_consumed_execution_ticket(str(tmp_path), "self_repair")
    assert ack["ok"] is False
    assert ack["reason"] == "fresh_consumed_ticket_handoff_missing"


def test_sink_handoff_is_single_use(tmp_path):
    _mint(str(tmp_path))
    consumed = consume_execution_ticket(str(tmp_path), "self_repair")
    assert consumed["ok"] is True
    first = acknowledge_consumed_execution_ticket(str(tmp_path), "self_repair")
    second = acknowledge_consumed_execution_ticket(str(tmp_path), "self_repair")
    assert first["ok"] is True
    assert second["ok"] is False


def test_background_self_repair_cannot_bypass_runtime_authority(tmp_path):
    result = self_repair_run(str(tmp_path))
    assert result["ok"] is False
    assert result["blocked"] is True
    assert result["reason"] == "constitutional_self_repair_handoff_missing"
