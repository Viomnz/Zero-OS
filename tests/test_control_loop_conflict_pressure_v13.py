from __future__ import annotations

from datetime import datetime, timedelta, timezone

from zero_os.control_loop_conflict_arbiter import ControllerIntent, ConflictDisposition, arbitrate_controller_conflicts
from zero_os.pure_logic_authority_kernel import ConstitutionalRequest, ControllerEvidence, IdentityAuthority
from zero_os.pure_logic_control_loop import (
    CandidateAction,
    ControlDecision,
    ControllerAuthorityState,
    ControllerContract,
    FeedbackSource,
    LoopState,
    LoopTier,
    StateEstimate,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _decision(scope: str) -> ControlDecision:
    return ControlDecision(
        allowed=True,
        loop_state=LoopState.READY,
        controller_authority=ControllerAuthorityState.PROVISIONAL,
        reason="eligible",
        permitted_capability_scope=scope,
    )


def _intent(controller: str, action_id: str, outcome: str, *, reversible: bool = True, uncertainty: float = 0.1) -> ControllerIntent:
    now = _now().isoformat()
    action = CandidateAction(
        action_id=action_id,
        capability_scope="runtime:network_control",
        predicted_outcome=outcome,
        reversible=reversible,
        blast="subsystem",
        requested_at_utc=now,
    )
    return ControllerIntent(
        controller_id=controller,
        objective_id="network-health",
        subject_id="network-stack",
        decision=_decision("runtime:network_control"),
        action=action,
        uncertainty=uncertainty,
        priority_hint=999.0,
    )


def test_reversible_conflicting_controllers_are_serialized_not_authorized():
    result = arbitrate_controller_conflicts([
        _intent("controller-a", "enable_route", "route:on"),
        _intent("controller-b", "disable_route", "route:off"),
    ])
    assert result.permitted is False
    assert result.disposition == ConflictDisposition.SERIALIZE
    assert result.authority_granted is False
    assert result.selected_controller == ""


def test_irreversible_conflict_forces_safe_mode_even_with_priority_hint():
    result = arbitrate_controller_conflicts([
        _intent("controller-a", "rewrite_state", "state:a", reversible=False),
        _intent("controller-b", "rewrite_state", "state:b", reversible=True),
    ])
    assert result.permitted is False
    assert result.disposition == ConflictDisposition.SAFE_MODE
    assert result.authority_granted is False


def test_high_uncertainty_conflict_requires_investigation():
    result = arbitrate_controller_conflicts([
        _intent("controller-a", "route-a", "route:a", uncertainty=0.7),
        _intent("controller-b", "route-b", "route:b", uncertainty=0.1),
    ])
    assert result.disposition == ConflictDisposition.INVESTIGATE


def test_constitutional_request_has_no_self_asserted_controller_boolean():
    fields = set(ConstitutionalRequest.__dataclass_fields__)
    assert "controller_eligible" not in fields
    assert "controller_loop_state" not in fields
    assert "controller_authority_state" not in fields
    assert "controller_evidence" in fields


def test_raw_controller_evidence_contains_recomputable_inputs():
    now = _now()
    source = FeedbackSource(
        source_id="probe",
        provenance="runtime",
        method_family="probe",
        lineage=("independent-probe",),
        fresh_until_utc=(now + timedelta(seconds=30)).isoformat(),
        demonstrated_scope=("runtime:self_repair",),
        reliability=1.0,
    )
    evidence = ControllerEvidence(
        contract=ControllerContract(
            controller_id="self_repair",
            objective_id="runtime-health",
            authority_id="repair-authority",
            scope=("runtime:self_repair",),
            allowed_actions=("self_repair",),
            max_blast="system",
            expires_at_utc=(now + timedelta(minutes=1)).isoformat(),
            revocation_conditions=("compromised",),
            expected_response_min_seconds=1.0,
            expected_response_max_seconds=30.0,
            loop_tier=LoopTier.OPERATIONAL,
        ),
        controller_authority=ControllerAuthorityState.PROVISIONAL,
        estimate=StateEstimate(
            state_id="runtime",
            value="degraded",
            uncertainty=0.1,
            sources=(source,),
            observed_at_utc=now.isoformat(),
        ),
        action=CandidateAction(
            action_id="self_repair",
            capability_scope="runtime:self_repair",
            predicted_outcome="healthy",
            reversible=True,
            blast="system",
            requested_at_utc=now.isoformat(),
        ),
    )
    request = ConstitutionalRequest(
        actor=IdentityAuthority("zero-ai", ("controller",), True, frozenset({"runtime:self_repair"})),
        action_scope="runtime:self_repair",
        objective_id="runtime-health",
        authority_id="repair-authority",
        requested_capability="self_repair",
        consequence="high",
        reversible=True,
        controller_evidence=evidence,
    )
    assert request.controller_evidence.action.action_id == "self_repair"
