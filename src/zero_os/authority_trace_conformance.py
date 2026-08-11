from __future__ import annotations

from zero_os.authority_runtime_trace import read_trace
from zero_os.authority_state_machine import AuthorityArtifactState, verify_transition_sequence


_EVENT_TO_STATE = {
    "constitutional_decision": AuthorityArtifactState.CONSTITUTIONALLY_ALLOWED,
    "issuer_attestation": AuthorityArtifactState.ATTESTED,
    "runtime_activate": AuthorityArtifactState.ACTIVE,
    "runtime_consume": AuthorityArtifactState.CONSUMED,
    "sink_acknowledge": AuthorityArtifactState.SINK_ACKNOWLEDGED,
    "outcome_verify": AuthorityArtifactState.OUTCOME_VERIFIED,
    "authority_expire": AuthorityArtifactState.EXPIRED,
    "authority_revoke": AuthorityArtifactState.REVOKED,
    "authority_contest": AuthorityArtifactState.CONTESTED,
}


def verify_trace_state_conformance(cwd: str, trace_id: str) -> dict:
    rows = read_trace(cwd, trace_id)
    if not rows:
        return {"ok": False, "reason": "authority_trace_missing", "trace_id": trace_id}

    states = [AuthorityArtifactState.PROPOSED]
    unknown_events: list[str] = []
    for row in rows:
        kind = str(row.get("event_kind", ""))
        state = _EVENT_TO_STATE.get(kind)
        if state is None:
            unknown_events.append(kind)
            continue
        if states[-1] == state:
            continue
        states.append(state)

    result = verify_transition_sequence(states)
    return {
        "ok": bool(result.get("ok", False)) and not unknown_events,
        "trace_id": trace_id,
        "states": [state.value for state in states],
        "unknown_events": unknown_events,
        "model_result": result,
        "status": "RUNTIME_TRACE_CONFORMS_TO_AUTHORITY_MODEL" if result.get("ok", False) and not unknown_events else "CONTESTED",
    }
