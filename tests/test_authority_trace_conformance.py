from __future__ import annotations

from zero_os.authority_runtime_trace import record_event
from zero_os.authority_trace_conformance import verify_trace_state_conformance


def _record(cwd: str, trace_id: str, kind: str) -> None:
    record_event(
        cwd,
        trace_id=trace_id,
        event_kind=kind,
        principal_id="principal",
        authority_id="authority",
        objective_id="objective",
        action_kind="code_change",
        subject_id="subject",
        state_revision="r1",
        artifact_id=trace_id,
        payload={},
    )


def test_legal_runtime_trace_conforms(tmp_path):
    trace_id = "trace-legal"
    for kind in (
        "constitutional_decision",
        "issuer_attestation",
        "runtime_activate",
        "runtime_consume",
        "sink_acknowledge",
        "outcome_verify",
    ):
        _record(str(tmp_path), trace_id, kind)
    result = verify_trace_state_conformance(str(tmp_path), trace_id)
    assert result["ok"] is True


def test_runtime_trace_cannot_skip_activation(tmp_path):
    trace_id = "trace-skip"
    for kind in (
        "constitutional_decision",
        "issuer_attestation",
        "runtime_consume",
        "sink_acknowledge",
        "outcome_verify",
    ):
        _record(str(tmp_path), trace_id, kind)
    result = verify_trace_state_conformance(str(tmp_path), trace_id)
    assert result["ok"] is False
