from datetime import datetime, timedelta, timezone

from zero_os.pure_logic_control_loop import (
    ActuatorRecord,
    CandidateAction,
    ControllerAuthorityState,
    ControllerContract,
    ControlHistoryEntry,
    FeedbackSource,
    LoopState,
    LoopTier,
    OutcomeObservation,
    StateEstimate,
    authorize_control_step,
    observe_control_outcome,
)


def _source(now, source_id="sensor-a", method="telemetry", lineage=("sensor-a",)):
    return FeedbackSource(
        source_id=source_id,
        provenance="test",
        method_family=method,
        lineage=lineage,
        fresh_until_utc=(now + timedelta(minutes=1)).isoformat(),
        demonstrated_scope=("test",),
        reliability=0.9,
    )


def _contract(now, **overrides):
    values = dict(
        controller_id="controller",
        objective_id="objective",
        authority_id="controller-authority",
        scope=("cap:test",),
        allowed_actions=("act",),
        max_blast="subsystem",
        expires_at_utc=(now + timedelta(minutes=5)).isoformat(),
        revocation_conditions=("CONTROL_OSCILLATION",),
        expected_response_min_seconds=2.0,
        expected_response_max_seconds=8.0,
        max_uncertainty_for_irreversible_action=0.2,
        loop_tier=LoopTier.OPERATIONAL,
    )
    values.update(overrides)
    return ControllerContract(**values)


def _action(now, reversible=True, blast="subsystem"):
    return CandidateAction("act", "cap:test", "healthy", reversible, blast, now.isoformat())


def test_command_is_not_outcome_and_latency_blocks_early_success():
    now = datetime.now(timezone.utc)
    decision, entry = observe_control_outcome(
        contract=_contract(now),
        authority_before=ControllerAuthorityState.PROVISIONAL,
        action=_action(now),
        actuator=ActuatorRecord("act", "act", True, now.isoformat()),
        observation=OutcomeObservation("healthy", (_source(now),), (now + timedelta(seconds=1)).isoformat()),
        now_utc=now + timedelta(seconds=1),
    )
    assert decision.allowed is False
    assert decision.loop_state == LoopState.WAITING_FOR_FEEDBACK
    assert entry.outcome_verified is False


def test_actuator_mismatch_contests_controller():
    now = datetime.now(timezone.utc)
    decision, _ = observe_control_outcome(
        contract=_contract(now),
        authority_before=ControllerAuthorityState.SURVIVED_IN_SCOPE,
        action=_action(now),
        actuator=ActuatorRecord("act", "different-action", True, now.isoformat()),
        observation=OutcomeObservation("healthy", (_source(now),), (now + timedelta(seconds=9)).isoformat()),
        now_utc=now + timedelta(seconds=9),
    )
    assert decision.allowed is False
    assert decision.controller_authority == ControllerAuthorityState.CONTESTED


def test_controller_cannot_self_verify_outcome():
    now = datetime.now(timezone.utc)
    self_source = _source(now, source_id="controller")
    decision, _ = observe_control_outcome(
        contract=_contract(now),
        authority_before=ControllerAuthorityState.PROVISIONAL,
        action=_action(now),
        actuator=ActuatorRecord("act", "act", True, now.isoformat()),
        observation=OutcomeObservation("healthy", (self_source,), (now + timedelta(seconds=9)).isoformat()),
        now_utc=now + timedelta(seconds=9),
    )
    assert decision.allowed is False
    assert decision.reason == "independent_outcome_measurement_missing"


def test_high_uncertainty_cannot_expand_irreversible_authority():
    now = datetime.now(timezone.utc)
    decision = authorize_control_step(
        contract=_contract(now),
        controller_authority=ControllerAuthorityState.PROVISIONAL,
        objective_authorized=True,
        estimate=StateEstimate("state", "x", 0.8, (_source(now),), now.isoformat()),
        action=_action(now, reversible=False),
        now_utc=now,
    )
    assert decision.allowed is False
    assert decision.loop_state == LoopState.SAFE_MODE
    assert decision.authority_reduction is True


def test_oscillation_forces_investigation():
    now = datetime.now(timezone.utc)
    history = [
        ControlHistoryEntry("A", "act", "B", "act", "B", False, "miss"),
        ControlHistoryEntry("B", "act", "A", "act", "A", False, "miss"),
        ControlHistoryEntry("A", "act", "B", "act", "B", False, "miss"),
        ControlHistoryEntry("B", "act", "A", "act", "A", False, "miss"),
    ]
    decision = authorize_control_step(
        contract=_contract(now),
        controller_authority=ControllerAuthorityState.SURVIVED_IN_SCOPE,
        objective_authorized=True,
        estimate=StateEstimate("state", "A", 0.1, (_source(now),), now.isoformat()),
        action=_action(now),
        history=history,
        now_utc=now,
    )
    assert decision.allowed is False
    assert decision.reason == "CONTROL_OSCILLATION"
    assert decision.controller_authority == ControllerAuthorityState.CONTESTED


def test_expired_controller_authority_is_revoked():
    now = datetime.now(timezone.utc)
    contract = _contract(now, expires_at_utc=(now - timedelta(seconds=1)).isoformat())
    decision = authorize_control_step(
        contract=contract,
        controller_authority=ControllerAuthorityState.SURVIVED_IN_SCOPE,
        objective_authorized=True,
        estimate=StateEstimate("state", "A", 0.1, (_source(now),), now.isoformat()),
        action=_action(now),
        now_utc=now,
    )
    assert decision.allowed is False
    assert decision.controller_authority == ControllerAuthorityState.REVOKED
