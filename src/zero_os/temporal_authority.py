from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable


class TemporalState(str, Enum):
    VALID_NOW = "VALID_NOW"
    WAITING = "WAITING"
    STALE = "STALE"
    CONTESTED = "CONTESTED"
    BLOCK = "BLOCK"


@dataclass(frozen=True)
class TemporalAuthoritySubject:
    subject_id: str
    state_revision: str
    valid_from: float
    valid_until: float
    max_age: float
    sequence_index: int
    expected_predecessor: str = ""
    observed_at: float = 0.0
    contradictions: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class TemporalDecision:
    eligible_to_continue_authority_evaluation: bool
    state: TemporalState
    reasons: tuple[str, ...]
    final_authority_granted: bool = False
    path_logic_final_authority: bool = False


def evaluate_temporal_authority(subject: TemporalAuthoritySubject, *, now: float, predecessor_id: str = "") -> TemporalDecision:
    reasons: list[str] = []
    if now < subject.valid_from:
        reasons.append("temporal_window_not_open")
    if now > subject.valid_until:
        reasons.append("temporal_authority_expired")
    if subject.observed_at and now - subject.observed_at > subject.max_age:
        reasons.append("temporal_evidence_stale")
    if subject.expected_predecessor and predecessor_id != subject.expected_predecessor:
        reasons.append("sequence_predecessor_mismatch")
    if subject.contradictions:
        reasons.append("temporal_contradiction_present")

    if "temporal_authority_expired" in reasons or "sequence_predecessor_mismatch" in reasons:
        state = TemporalState.BLOCK
    elif "temporal_evidence_stale" in reasons or "temporal_contradiction_present" in reasons:
        state = TemporalState.CONTESTED
    elif "temporal_window_not_open" in reasons:
        state = TemporalState.WAITING
    else:
        state = TemporalState.VALID_NOW

    return TemporalDecision(
        eligible_to_continue_authority_evaluation=not reasons,
        state=state,
        reasons=tuple(reasons),
        final_authority_granted=False,
        path_logic_final_authority=False,
    )


def temporal_invariants() -> tuple[str, ...]:
    return (
        "authority_validity_is_time_bounded",
        "stale_evidence_cannot_retain_current_authority",
        "sequence_authority_is_distinct_from_component_authority",
        "valid_graph_structure_does_not_imply_valid_temporal_order",
        "temporal_gate_never_grants_final_authority",
    )
