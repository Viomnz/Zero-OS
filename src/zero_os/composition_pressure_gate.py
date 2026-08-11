from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable


class CompositionState(str, Enum):
    CLEAR = "CLEAR"
    CONTESTED = "CONTESTED"
    BLOCK = "BLOCK"
    INVESTIGATE = "INVESTIGATE"


@dataclass(frozen=True)
class AuthorizedPart:
    part_id: str
    authority_id: str
    demonstrated_scope: tuple[str, ...]
    local_invariants_passed: bool
    state_revision: str = ""


@dataclass(frozen=True)
class CompositionRequest:
    composition_id: str
    parts: tuple[AuthorizedPart, ...]
    requested_joint_state: str
    certified_joint_states: tuple[str, ...] = field(default_factory=tuple)
    joint_invariants_passed: bool = False
    interaction_model_available: bool = False
    reversible: bool = True
    uncertainty: float = 1.0


@dataclass(frozen=True)
class CompositionDecision:
    eligible_to_continue_authority_evaluation: bool
    state: CompositionState
    reasons: tuple[str, ...]
    demonstrated_joint_scope: tuple[str, ...]
    final_authority_granted: bool = False
    path_logic_final_authority: bool = False


def evaluate_composition(request: CompositionRequest) -> CompositionDecision:
    reasons: list[str] = []
    if len(request.parts) < 2:
        reasons.append("composition_requires_multiple_parts")
    if any(not part.local_invariants_passed for part in request.parts):
        reasons.append("local_part_not_survived")
    if any(not part.authority_id for part in request.parts):
        reasons.append("part_authority_missing")
    if any(not part.demonstrated_scope for part in request.parts):
        reasons.append("part_scope_missing")

    joint_certified = request.requested_joint_state in set(request.certified_joint_states)
    if not request.interaction_model_available:
        reasons.append("interaction_model_missing")
    if not request.joint_invariants_passed:
        reasons.append("joint_invariants_not_survived")
    if not joint_certified:
        reasons.append("requested_joint_state_outside_demonstrated_composition_scope")
    if not request.reversible and float(request.uncertainty) > 0.2:
        reasons.append("irreversible_composition_under_excess_uncertainty")

    if "joint_invariants_not_survived" in reasons or "irreversible_composition_under_excess_uncertainty" in reasons:
        state = CompositionState.BLOCK
    elif reasons:
        state = CompositionState.INVESTIGATE
    else:
        state = CompositionState.CLEAR

    return CompositionDecision(
        eligible_to_continue_authority_evaluation=not reasons,
        state=state,
        reasons=tuple(reasons),
        demonstrated_joint_scope=tuple(request.certified_joint_states),
        final_authority_granted=False,
        path_logic_final_authority=False,
    )


def composition_invariants() -> tuple[str, ...]:
    return (
        "local_authority_does_not_imply_joint_authority",
        "locally_valid_components_can_form_globally_invalid_state",
        "joint_state_requires_independent_scope_and_invariant_pressure",
        "composition_gate_may_block_but_never_grant_final_authority",
        "path_logic_may_rank_only_after_composition_survives",
        "composition_failure_candidate_does_not_create_a_new_master_law",
    )
