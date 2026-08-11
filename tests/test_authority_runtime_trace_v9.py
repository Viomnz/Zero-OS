from zero_os.authority_runtime_trace import certify_authority_trace, record_event, verify_trace_chain


def _record(cwd: str, trace_id: str, kind: str):
    return record_event(
        cwd,
        trace_id=trace_id,
        event_kind=kind,
        principal_id="operator-a",
        authority_id="claim-a",
        objective_id="objective-a",
        action_kind="policy_change",
        subject_id="security-control",
        state_revision="r9",
        artifact_id="artifact-a",
        payload={"kind": kind},
    )


def test_complete_authority_trace_certifies_only_recorded_scope(tmp_path):
    trace_id = "trace-1"
    for kind in ("constitutional_decision", "issuer_attestation", "runtime_consume", "sink_acknowledge", "outcome_verify"):
        _record(str(tmp_path), trace_id, kind)
    result = certify_authority_trace(str(tmp_path), trace_id)
    assert result["ok"] is True
    assert result["status"] == "CAUSAL_TRACE_SURVIVED_IN_RECORDED_SCOPE"
    assert verify_trace_chain(str(tmp_path))["ok"] is True


def test_missing_sink_acknowledgement_keeps_trace_contested(tmp_path):
    trace_id = "trace-2"
    for kind in ("constitutional_decision", "issuer_attestation", "runtime_consume", "outcome_verify"):
        _record(str(tmp_path), trace_id, kind)
    result = certify_authority_trace(str(tmp_path), trace_id)
    assert result["ok"] is False
    assert "sink_acknowledge" in result["missing_events"]


def test_binding_drift_keeps_trace_contested(tmp_path):
    trace_id = "trace-3"
    _record(str(tmp_path), trace_id, "constitutional_decision")
    record_event(
        str(tmp_path),
        trace_id=trace_id,
        event_kind="issuer_attestation",
        principal_id="different-principal",
        authority_id="claim-a",
        objective_id="objective-a",
        action_kind="policy_change",
        subject_id="security-control",
        state_revision="r9",
        artifact_id="artifact-a",
        payload={},
    )
    result = certify_authority_trace(str(tmp_path), trace_id, required_events=("constitutional_decision", "issuer_attestation"))
    assert result["ok"] is False
    assert result["binding_consistent"] is False
