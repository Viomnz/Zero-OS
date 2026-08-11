from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable


class AuthorityArtifactState(str, Enum):
    PROPOSED = "PROPOSED"
    CONSTITUTIONALLY_ALLOWED = "CONSTITUTIONALLY_ALLOWED"
    ATTESTED = "ATTESTED"
    ACTIVE = "ACTIVE"
    CONSUMED = "CONSUMED"
    SINK_ACKNOWLEDGED = "SINK_ACKNOWLEDGED"
    OUTCOME_VERIFIED = "OUTCOME_VERIFIED"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"
    CONTESTED = "CONTESTED"


_TERMINAL = {
    AuthorityArtifactState.EXPIRED,
    AuthorityArtifactState.REVOKED,
    AuthorityArtifactState.CONTESTED,
}

_ALLOWED: dict[AuthorityArtifactState, frozenset[AuthorityArtifactState]] = {
    AuthorityArtifactState.PROPOSED: frozenset({
        AuthorityArtifactState.CONSTITUTIONALLY_ALLOWED,
        AuthorityArtifactState.CONTESTED,
    }),
    AuthorityArtifactState.CONSTITUTIONALLY_ALLOWED: frozenset({
        AuthorityArtifactState.ATTESTED,
        AuthorityArtifactState.CONTESTED,
        AuthorityArtifactState.EXPIRED,
        AuthorityArtifactState.REVOKED,
    }),
    AuthorityArtifactState.ATTESTED: frozenset({
        AuthorityArtifactState.ACTIVE,
        AuthorityArtifactState.EXPIRED,
        AuthorityArtifactState.REVOKED,
        AuthorityArtifactState.CONTESTED,
    }),
    AuthorityArtifactState.ACTIVE: frozenset({
        AuthorityArtifactState.CONSUMED,
        AuthorityArtifactState.EXPIRED,
        AuthorityArtifactState.REVOKED,
        AuthorityArtifactState.CONTESTED,
    }),
    AuthorityArtifactState.CONSUMED: frozenset({
        AuthorityArtifactState.SINK_ACKNOWLEDGED,
        AuthorityArtifactState.EXPIRED,
        AuthorityArtifactState.REVOKED,
        AuthorityArtifactState.CONTESTED,
    }),
    AuthorityArtifactState.SINK_ACKNOWLEDGED: frozenset({
        AuthorityArtifactState.OUTCOME_VERIFIED,
        AuthorityArtifactState.CONTESTED,
    }),
    AuthorityArtifactState.OUTCOME_VERIFIED: frozenset(),
    AuthorityArtifactState.EXPIRED: frozenset(),
    AuthorityArtifactState.REVOKED: frozenset(),
    AuthorityArtifactState.CONTESTED: frozenset(),
}


@dataclass(frozen=True)
class TransitionDecision:
    allowed: bool
    from_state: AuthorityArtifactState
    to_state: AuthorityArtifactState
    reason: str


def check_transition(
    from_state: AuthorityArtifactState | str,
    to_state: AuthorityArtifactState | str,
) -> TransitionDecision:
    source = AuthorityArtifactState(str(from_state))
    target = AuthorityArtifactState(str(to_state))
    if source in _TERMINAL:
        return TransitionDecision(False, source, target, "terminal_authority_state_cannot_transition")
    if target not in _ALLOWED[source]:
        return TransitionDecision(False, source, target, "illegal_authority_state_transition")
    return TransitionDecision(True, source, target, "authority_state_transition_allowed")


def verify_transition_sequence(states: Iterable[AuthorityArtifactState | str]) -> dict:
    sequence = [AuthorityArtifactState(str(item)) for item in states]
    if not sequence:
        return {"ok": False, "reason": "authority_state_sequence_empty"}
    if sequence[0] != AuthorityArtifactState.PROPOSED:
        return {"ok": False, "reason": "authority_state_sequence_must_begin_proposed"}
    for index in range(len(sequence) - 1):
        decision = check_transition(sequence[index], sequence[index + 1])
        if not decision.allowed:
            return {
                "ok": False,
                "reason": decision.reason,
                "index": index,
                "from_state": decision.from_state.value,
                "to_state": decision.to_state.value,
            }
    return {
        "ok": True,
        "reason": "authority_state_sequence_legal",
        "states": [item.value for item in sequence],
        "final_state": sequence[-1].value,
    }


def illegal_state_invariants() -> dict:
    return {
        "active_without_attestation_forbidden": True,
        "consume_before_active_forbidden": True,
        "sink_ack_before_consume_forbidden": True,
        "outcome_verify_before_sink_ack_forbidden": True,
        "terminal_state_revival_forbidden": True,
        "revoked_or_expired_authority_cannot_execute": True,
    }
