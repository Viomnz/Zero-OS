from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Iterable


class ControllerAuthorityState(str, Enum):
    UNTESTED = "UNTESTED"
    PROVISIONAL = "PROVISIONAL"
    SURVIVED_IN_SCOPE = "SURVIVED_IN_SCOPE"
    CONTESTED = "CONTESTED"
    DEGRADED = "DEGRADED"
    QUARANTINED = "QUARANTINED"
    REVOKED = "REVOKED"


class LoopState(str, Enum):
    READY = "READY"
    WAITING_FOR_FEEDBACK = "WAITING_FOR_FEEDBACK"
    INVESTIGATING = "INVESTIGATING"
    RESOLVED = "RESOLVED"
    DEGRADED = "DEGRADED"
    SAFE_MODE = "SAFE_MODE"
    ESCALATED = "ESCALATED"
    QUARANTINED = "QUARANTINED"


class LoopTier(str, Enum):
    FAST_SAFETY = "FAST_SAFETY"
    OPERATIONAL = "OPERATIONAL"
    INVESTIGATION = "INVESTIGATION"
    OBJECTIVE = "OBJECTIVE"
    ARCHITECTURE = "ARCHITECTURE"


@dataclass(frozen=True)
class FeedbackSource:
    source_id: str
    provenance: str
    method_family: str
    lineage: tuple[str, ...] = ()
    fresh_until_utc: str = ""
    demonstrated_scope: tuple[str, ...] = ()
    reliability: float = 0.0
    contradicted: bool = False


@dataclass(frozen=True)
class ControllerContract:
    controller_id: str
    objective_id: str
    authority_id: str
    scope: tuple[str, ...]
    allowed_actions: tuple[str, ...]
    max_blast: str
    expires_at_utc: str
    revocation_conditions: tuple[str, ...]
    expected_response_min_seconds: float
    expected_response_max_seconds: float
    max_uncertainty_for_irreversible_action: float = 0.20
    loop_tier: LoopTier = LoopTier.OPERATIONAL


@dataclass(frozen=True)
class StateEstimate:
    state_id: str
    value: str
    uncertainty: float
    sources: tuple[FeedbackSource, ...]
    observed_at_utc: str


@dataclass(frozen=True)
class CandidateAction:
    action_id: str
    capability_scope: str
    predicted_outcome: str
    reversible: bool
    blast: str
    requested_at_utc: str


@dataclass(frozen=True)
class ActuatorRecord:
    requested_action: str
    executed_action: str
    applied: bool
    observed_at_utc: str


@dataclass(frozen=True)
class OutcomeObservation:
    observed_outcome: str
    sources: tuple[FeedbackSource, ...]
    observed_at_utc: str


@dataclass(frozen=True)
class ControlHistoryEntry:
    state_before: str
    requested_action: str
    predicted_outcome: str
    executed_action: str
    observed_outcome: str
    outcome_verified: bool
    contradiction: str = ""


@dataclass(frozen=True)
class ControlDecision:
    allowed: bool
    loop_state: LoopState
    controller_authority: ControllerAuthorityState
    reason: str
    permitted_capability_scope: str = ""
    wait_until_utc: str = ""
    investigation_required: bool = False
    authority_reduction: bool = False
    evidence: dict = field(default_factory=dict)


def _parse_utc(value: str) -> datetime | None:
    if not value:
        return None
    try:
        out = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if out.tzinfo is None:
        out = out.replace(tzinfo=timezone.utc)
    return out.astimezone(timezone.utc)


def _now(now_utc: datetime | None = None) -> datetime:
    return (now_utc or datetime.now(timezone.utc)).astimezone(timezone.utc)


def _source_fresh(source: FeedbackSource, now: datetime) -> bool:
    expiry = _parse_utc(source.fresh_until_utc)
    return expiry is not None and now <= expiry


def _independent_groups(sources: Iterable[FeedbackSource], now: datetime) -> set[tuple[str, tuple[str, ...]]]:
    groups: set[tuple[str, tuple[str, ...]]] = set()
    for source in sources:
        if source.contradicted or not _source_fresh(source, now):
            continue
        groups.add((source.method_family, tuple(sorted(source.lineage))))
    return groups


def _blast_rank(value: str) -> int:
    return {"local": 0, "process": 1, "subsystem": 2, "system": 3, "external": 4}.get(str(value).lower(), 99)


def _detect_oscillation(history: Iterable[ControlHistoryEntry], *, min_repeats: int = 2) -> bool:
    rows = list(history)
    if len(rows) < 4:
        return False
    states = [row.state_before for row in rows] + [rows[-1].observed_outcome]
    # Detect A->B->A->B and longer period-2 recurrence.
    if len(states) >= 5:
        tail = states[-5:]
        if tail[0] == tail[2] == tail[4] and tail[1] == tail[3] and tail[0] != tail[1]:
            return True
    # Repeated identical correction without verified convergence is also oscillatory pressure.
    recent = rows[-max(4, min_repeats + 2):]
    same_action = len({row.requested_action for row in recent}) == 1
    no_verified = not any(row.outcome_verified for row in recent)
    return same_action and no_verified and len(recent) >= 4


def authorize_control_step(
    *,
    contract: ControllerContract,
    controller_authority: ControllerAuthorityState,
    objective_authorized: bool,
    estimate: StateEstimate,
    action: CandidateAction,
    history: Iterable[ControlHistoryEntry] = (),
    active_revocation_conditions: Iterable[str] = (),
    now_utc: datetime | None = None,
) -> ControlDecision:
    """Authorize one controller step without making Path Law final authority.

    This function does not mint capability/execution authority. It determines
    whether a controller remains eligible to request the independently scoped
    capability named by the candidate action.
    """
    now = _now(now_utc)
    expiry = _parse_utc(contract.expires_at_utc)
    if expiry is None or now > expiry:
        return ControlDecision(False, LoopState.QUARANTINED, ControllerAuthorityState.REVOKED, "controller_authority_expired", authority_reduction=True)
    if not objective_authorized:
        return ControlDecision(False, LoopState.ESCALATED, ControllerAuthorityState.CONTESTED, "objective_authority_missing", investigation_required=True, authority_reduction=True)
    if controller_authority in {ControllerAuthorityState.QUARANTINED, ControllerAuthorityState.REVOKED}:
        return ControlDecision(False, LoopState.QUARANTINED, controller_authority, "controller_not_operational")
    revocations = set(active_revocation_conditions)
    if revocations.intersection(contract.revocation_conditions):
        return ControlDecision(False, LoopState.QUARANTINED, ControllerAuthorityState.REVOKED, "controller_revocation_condition_active", authority_reduction=True)
    if action.action_id not in set(contract.allowed_actions):
        return ControlDecision(False, LoopState.INVESTIGATING, ControllerAuthorityState.CONTESTED, "action_outside_controller_demonstrated_scope", investigation_required=True, authority_reduction=True)
    if action.capability_scope not in set(contract.scope):
        return ControlDecision(False, LoopState.INVESTIGATING, ControllerAuthorityState.CONTESTED, "capability_outside_controller_scope", investigation_required=True, authority_reduction=True)
    if _blast_rank(action.blast) > _blast_rank(contract.max_blast):
        return ControlDecision(False, LoopState.SAFE_MODE, ControllerAuthorityState.DEGRADED, "blast_exceeds_controller_contract", investigation_required=True, authority_reduction=True)
    if _detect_oscillation(history):
        return ControlDecision(False, LoopState.INVESTIGATING, ControllerAuthorityState.CONTESTED, "CONTROL_OSCILLATION", investigation_required=True, authority_reduction=True)

    valid_sources = [source for source in estimate.sources if _source_fresh(source, now) and not source.contradicted]
    groups = _independent_groups(valid_sources, now)
    if not valid_sources:
        return ControlDecision(False, LoopState.INVESTIGATING, ControllerAuthorityState.CONTESTED, "fresh_feedback_missing", investigation_required=True, authority_reduction=True)
    if estimate.uncertainty < 0.0 or estimate.uncertainty > 1.0:
        return ControlDecision(False, LoopState.INVESTIGATING, ControllerAuthorityState.CONTESTED, "state_uncertainty_invalid", investigation_required=True)
    if not action.reversible and estimate.uncertainty > contract.max_uncertainty_for_irreversible_action:
        return ControlDecision(False, LoopState.SAFE_MODE, ControllerAuthorityState.DEGRADED, "uncertainty_too_high_for_irreversible_action", investigation_required=True, authority_reduction=True)

    authority = controller_authority
    if estimate.uncertainty >= 0.50:
        authority = ControllerAuthorityState.DEGRADED
    elif len(groups) < 2 and contract.loop_tier in {LoopTier.INVESTIGATION, LoopTier.OBJECTIVE, LoopTier.ARCHITECTURE}:
        authority = ControllerAuthorityState.CONTESTED
        return ControlDecision(False, LoopState.INVESTIGATING, authority, "independent_feedback_groups_insufficient", investigation_required=True, authority_reduction=True)

    return ControlDecision(
        True,
        LoopState.READY,
        authority,
        "controller_step_eligible_for_independent_capability_authorization",
        permitted_capability_scope=action.capability_scope,
        evidence={
            "uncertainty": estimate.uncertainty,
            "fresh_source_count": len(valid_sources),
            "independent_feedback_groups": len(groups),
            "path_logic_grants_authority": False,
        },
    )


def observe_control_outcome(
    *,
    contract: ControllerContract,
    authority_before: ControllerAuthorityState,
    action: CandidateAction,
    actuator: ActuatorRecord,
    observation: OutcomeObservation,
    history: Iterable[ControlHistoryEntry] = (),
    now_utc: datetime | None = None,
) -> tuple[ControlDecision, ControlHistoryEntry]:
    """Compare requested action, executed action, and independently observed effect."""
    now = _now(now_utc)
    requested_at = _parse_utc(action.requested_at_utc)
    if requested_at is None:
        decision = ControlDecision(False, LoopState.INVESTIGATING, ControllerAuthorityState.CONTESTED, "action_request_time_invalid", investigation_required=True)
        entry = ControlHistoryEntry("", action.action_id, action.predicted_outcome, actuator.executed_action, observation.observed_outcome, False, decision.reason)
        return decision, entry

    elapsed = (now - requested_at).total_seconds()
    wait_until = requested_at + timedelta(seconds=max(0.0, contract.expected_response_max_seconds))
    if elapsed < contract.expected_response_min_seconds:
        decision = ControlDecision(False, LoopState.WAITING_FOR_FEEDBACK, authority_before, "feedback_observed_before_expected_window", wait_until_utc=wait_until.isoformat())
        entry = ControlHistoryEntry("", action.action_id, action.predicted_outcome, actuator.executed_action, observation.observed_outcome, False, "feedback_too_early")
        return decision, entry

    if not actuator.applied or actuator.executed_action != action.action_id:
        decision = ControlDecision(False, LoopState.INVESTIGATING, ControllerAuthorityState.CONTESTED, "actuator_execution_mismatch", investigation_required=True, authority_reduction=True)
        entry = ControlHistoryEntry("", action.action_id, action.predicted_outcome, actuator.executed_action, observation.observed_outcome, False, decision.reason)
        return decision, entry

    groups = _independent_groups(observation.sources, now)
    independent_enough = len(groups) >= 1 and all(source.source_id != contract.controller_id for source in observation.sources)
    if not independent_enough:
        decision = ControlDecision(False, LoopState.INVESTIGATING, ControllerAuthorityState.CONTESTED, "independent_outcome_measurement_missing", investigation_required=True, authority_reduction=True)
        entry = ControlHistoryEntry("", action.action_id, action.predicted_outcome, actuator.executed_action, observation.observed_outcome, False, decision.reason)
        return decision, entry

    if elapsed <= contract.expected_response_max_seconds and observation.observed_outcome != action.predicted_outcome:
        decision = ControlDecision(False, LoopState.WAITING_FOR_FEEDBACK, authority_before, "predicted_effect_not_yet_observed_within_latency_window", wait_until_utc=wait_until.isoformat())
        entry = ControlHistoryEntry("", action.action_id, action.predicted_outcome, actuator.executed_action, observation.observed_outcome, False, "pending_latency_window")
        return decision, entry

    verified = observation.observed_outcome == action.predicted_outcome
    if verified:
        next_authority = ControllerAuthorityState.SURVIVED_IN_SCOPE if authority_before in {ControllerAuthorityState.PROVISIONAL, ControllerAuthorityState.SURVIVED_IN_SCOPE} else authority_before
        decision = ControlDecision(True, LoopState.RESOLVED, next_authority, "predicted_outcome_independently_observed")
        entry = ControlHistoryEntry("", action.action_id, action.predicted_outcome, actuator.executed_action, observation.observed_outcome, True)
        return decision, entry

    previous_failures = sum(1 for row in history if row.contradiction)
    next_authority = ControllerAuthorityState.DEGRADED if previous_failures < 2 else ControllerAuthorityState.QUARANTINED
    decision = ControlDecision(False, LoopState.INVESTIGATING if next_authority == ControllerAuthorityState.DEGRADED else LoopState.QUARANTINED, next_authority, "prediction_reality_contradiction", investigation_required=True, authority_reduction=True)
    entry = ControlHistoryEntry("", action.action_id, action.predicted_outcome, actuator.executed_action, observation.observed_outcome, False, decision.reason)
    return decision, entry


def control_contract_to_dict(contract: ControllerContract) -> dict:
    return asdict(contract)
