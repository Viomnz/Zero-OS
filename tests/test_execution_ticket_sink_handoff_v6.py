from zero_os.execution_authority_ticket import (
    acknowledge_consumed_execution_ticket,
    consume_execution_ticket,
    issue_execution_ticket,
)
from zero_os.self_repair import self_repair_run


def test_sink_handoff_requires_prior_runtime_consumption(tmp_path):
    issue_execution_ticket(
        str(tmp_path),
        action_kind="self_repair",
        authority_id="a1",
        subject_id="repair-1",
        required_scope="system:self_repair",
        state_revision="r1",
    )
    ack = acknowledge_consumed_execution_ticket(str(tmp_path), "self_repair")
    assert ack["ok"] is False
    assert ack["reason"] == "fresh_consumed_ticket_handoff_missing"


def test_sink_handoff_is_single_use(tmp_path):
    issue_execution_ticket(
        str(tmp_path),
        action_kind="self_repair",
        authority_id="a1",
        subject_id="repair-1",
        required_scope="system:self_repair",
        state_revision="r1",
    )
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
