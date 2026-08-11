from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable

from zero_os.pure_logic_control_loop import CandidateAction, ControlDecision, LoopState


class ConflictDisposition(str, Enum):
    NO_CONFLICT = "NO_CONFLICT"
    SERIALIZE = "SERIALIZE"
    INVESTIGATE = "INVESTIGATE"
    SAFE_MODE = "SAFE_MODE"
    QUARANTINE = "QUARANTINE"


@dataclass(frozen=True)
class ControllerIntent:
    controller_id: str
    objective_id: str
    subject_id: str
    decision: ControlDecision
    action: CandidateAction
    uncertainty: float
    priority_hint: float = 0.0


@dataclass(frozen=True)
class ConflictDecision:
    permitted: bool
    disposition: ConflictDisposition
    reason: str
    conflicting_controllers: tuple[str, ...] = ()
    authority_granted: bool = False
    selected_controller: str = ""


def _same_target(a: ControllerIntent, b: ControllerIntent) -> bool:
    return a.subject_id == b.subject_id or a.action.capability_scope == b.action.capability_scope


def _incompatible(a: ControllerIntent, b: ControllerIntent) -> bool:
    if not _same_target(a, b):
        return False
    if a.action.action_id == b.action.action_id and a.action.predicted_outcome == b.action.predicted_outcome:
        return False
    if a.action.predicted_outcome != b.action.predicted_outcome:
        return True
    return a.action.action_id != b.action.action_id


def arbitrate_controller_conflicts(intents: Iterable[ControllerIntent]) -> ConflictDecision:
    """Detect controller conflicts without becoming final authority.

    The arbiter may only block, serialize, or escalate. It deliberately cannot
    select a controller and cannot mint or grant capability/execution authority.
    """
    rows = [item for item in intents if item.decision.allowed and item.decision.loop_state == LoopState.READY]
    if len(rows) <= 1:
        return ConflictDecision(True, ConflictDisposition.NO_CONFLICT, "no_concurrent_controller_conflict")

    conflicts: set[str] = set()
    irreversible_conflict = False
    high_uncertainty = False
    for index, left in enumerate(rows):
        for right in rows[index + 1 :]:
            if not _incompatible(left, right):
                continue
            conflicts.update({left.controller_id, right.controller_id})
            if not left.action.reversible or not right.action.reversible:
                irreversible_conflict = True
            if max(left.uncertainty, right.uncertainty) >= 0.5:
                high_uncertainty = True

    if not conflicts:
        return ConflictDecision(True, ConflictDisposition.NO_CONFLICT, "controllers_non_conflicting")
    ordered = tuple(sorted(conflicts))
    if irreversible_conflict:
        return ConflictDecision(False, ConflictDisposition.SAFE_MODE, "conflicting_irreversible_controllers", ordered)
    if high_uncertainty:
        return ConflictDecision(False, ConflictDisposition.INVESTIGATE, "conflicting_controllers_under_high_uncertainty", ordered)
    return ConflictDecision(False, ConflictDisposition.SERIALIZE, "conflicting_reversible_controllers_require_serial_execution", ordered)


def conflict_arbiter_invariants() -> tuple[str, ...]:
    return (
        "conflict_arbiter_never_grants_final_authority",
        "conflicting_irreversible_actions_enter_safe_mode",
        "conflicting_reversible_actions_are_serialized_not_concurrently_executed",
        "high_uncertainty_conflict_requires_investigation",
        "priority_hint_cannot_override_authority_or_conflict",
        "path_logic_may_rank_after_conflict_resolution_but_cannot_authorize",
    )
