from __future__ import annotations

from zero_os.authority_state_machine import AuthorityArtifactState, check_transition, illegal_state_invariants


_FORBIDDEN_EDGES = {
    (AuthorityArtifactState.PROPOSED, AuthorityArtifactState.ACTIVE),
    (AuthorityArtifactState.PROPOSED, AuthorityArtifactState.CONSUMED),
    (AuthorityArtifactState.CONSTITUTIONALLY_ALLOWED, AuthorityArtifactState.CONSUMED),
    (AuthorityArtifactState.ATTESTED, AuthorityArtifactState.CONSUMED),
    (AuthorityArtifactState.ACTIVE, AuthorityArtifactState.SINK_ACKNOWLEDGED),
    (AuthorityArtifactState.CONSUMED, AuthorityArtifactState.OUTCOME_VERIFIED),
    (AuthorityArtifactState.REVOKED, AuthorityArtifactState.ACTIVE),
    (AuthorityArtifactState.EXPIRED, AuthorityArtifactState.ACTIVE),
    (AuthorityArtifactState.CONTESTED, AuthorityArtifactState.ACTIVE),
}


def model_check_authority_state_machine() -> dict:
    states = list(AuthorityArtifactState)
    checked = 0
    forbidden_accepted: list[dict] = []
    terminal_revival: list[dict] = []

    for source in states:
        for target in states:
            if source == target:
                continue
            decision = check_transition(source, target)
            checked += 1
            if (source, target) in _FORBIDDEN_EDGES and decision.allowed:
                forbidden_accepted.append({"from": source.value, "to": target.value})
            if source in {
                AuthorityArtifactState.REVOKED,
                AuthorityArtifactState.EXPIRED,
                AuthorityArtifactState.CONTESTED,
            } and decision.allowed:
                terminal_revival.append({"from": source.value, "to": target.value})

    invariants = illegal_state_invariants()
    invariant_declarations_complete = all(bool(value) for value in invariants.values())
    ok = not forbidden_accepted and not terminal_revival and invariant_declarations_complete
    return {
        "ok": ok,
        "status": "FORMAL_FINITE_STATE_MODEL_SURVIVED" if ok else "FORMAL_MODEL_VIOLATION",
        "state_count": len(states),
        "transition_pairs_checked": checked,
        "forbidden_edges_checked": len(_FORBIDDEN_EDGES),
        "forbidden_edges_accepted": forbidden_accepted,
        "terminal_revival_edges": terminal_revival,
        "declared_invariants": invariants,
        "scope": "authority_artifact_finite_state_transition_model",
        "limitations": [
            "does_not_prove_python_runtime_matches_model",
            "does_not_cover_native_or_external_components",
            "does_not_prove_concurrency_interleavings",
            "requires_runtime_trace_conformance_check",
        ],
    }
