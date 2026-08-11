from __future__ import annotations

from datetime import datetime, timedelta, timezone

from zero_os.pure_logic_authority_kernel import ConstitutionalRequest, ControllerEvidence, IdentityAuthority
from zero_os.pure_logic_control_loop import (
    CandidateAction,
    ControllerAuthorityState,
    ControllerContract,
    FeedbackSource,
    LoopTier,
    StateEstimate,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _controller_evidence() -> ControllerEvidence:
    now = _now()
    source = FeedbackSource(
        source_id="runtime-readiness-probe",
        provenance="runtime_state",
        method_family="readiness_probe",
        lineage=("readiness",),
        fresh_until_utc=(now + timedelta(seconds=30)).isoformat(),
        demonstrated_scope=("runtime:self_repair",),
        reliability=0.9,
    )
    contract = ControllerContract(
        controller_id="self_repair",
        objective_id="runtime-health",
        authority_id="repair-authority",
        scope=("runtime:self_repair",),
        allowed_actions=("self_repair",),
        max_blast="system",
        expires_at_utc=(now + timedelta(minutes=2)).isoformat(),
        revocation_conditions=("controller_compromised",),
        expected_response_min_seconds=1.0,
        expected_response_max_seconds=30.0,
        max_uncertainty_for_irreversible_action=0.2,
        loop_tier=LoopTier.OPERATIONAL,
    )
    estimate = StateEstimate(
        state_id="runtime-health",
        value="degraded",
        uncertainty=0.1,
        sources=(source,),
        observed_at_utc=now.isoformat(),
    )
    action = CandidateAction(
        action_id="self_repair",
        capability_scope="runtime:self_repair",
        predicted_outcome="bounded_runtime_repair_healthy",
        reversible=True,
        blast="system",
        requested_at_utc=now.isoformat(),
    )
    return ControllerEvidence(
        contract=contract,
        controller_authority=ControllerAuthorityState.PROVISIONAL,
        estimate=estimate,
        action=action,
    )


def _request(**overrides):
    data = {
        "actor": IdentityAuthority(
            principal_id="zero-ai",
            provenance=("autonomous_controller",),
            authenticated=True,
            demonstrated_scopes=frozenset({"runtime:self_repair"}),
        ),
        "action_scope": "runtime:self_repair",
        "objective_id": "runtime-health",
        "authority_id": "repair-authority",
        "requested_capability": "self_repair",
        "consequence": "high",
        "reversible": True,
        "controller_evidence": None,
    }
    data.update(overrides)
    return ConstitutionalRequest(**data)


def test_autonomous_request_defaults_fail_closed_without_controller_evidence():
    request = _request()
    assert request.requested_capability == "self_repair"
    assert request.controller_evidence is None


def test_autonomous_request_carries_raw_evidence_not_self_asserted_eligibility():
    request = _request(controller_evidence=_controller_evidence())
    assert request.controller_evidence is not None
    assert not hasattr(request, "controller_eligible")
    assert not hasattr(request, "execution_authority_granted")
    assert not hasattr(request, "promotion_permitted")


def test_controller_scope_is_bound_inside_raw_evidence():
    request = _request(controller_evidence=_controller_evidence())
    assert request.controller_evidence.action.capability_scope == "runtime:self_repair"
    assert request.controller_evidence.contract.scope == ("runtime:self_repair",)
