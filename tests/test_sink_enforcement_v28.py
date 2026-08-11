from zero_os.containment_sink_enforcement import evaluate_sensitive_sink, sink_enforcement_invariants
from zero_os.live_containment_state import LiveContainmentRegistry
from zero_os.protected_data_broker_runtime import BrokerDecryptResponse
from zero_os.protected_export_sinks import execute_protected_export
from zero_os.sink_enforcement_audit import audit_sink_enforcement
from zero_os.sink_enforcement_promotion import SinkEnforcementEvidence, evaluate_sink_enforcement_promotion


def _registry(identity="4242:123:abc"):
    registry = LiveContainmentRegistry()
    state = registry.register(identity)
    return registry, state


def test_contested_process_is_denied_at_sensitive_sink():
    registry, state = _registry()
    registry.contest(state.process_identity, "unexpected_decoy_beacon_access")
    decision = evaluate_sensitive_sink(
        containment=registry,
        process_identity=state.process_identity,
        operation="key_release",
    )
    assert not decision.allowed
    assert "process_authority_contested" in decision.reasons
    assert "protected_key_release_revoked" in decision.reasons
    assert not decision.authority_granted
    assert not decision.path_logic_final_authority


def test_pre_revocation_revision_becomes_stale():
    registry, state = _registry()
    old_revision = state.revision
    assert evaluate_sensitive_sink(
        containment=registry,
        process_identity=state.process_identity,
        operation="protected_read",
        expected_revision=old_revision,
    ).allowed
    registry.contest(state.process_identity, "unexpected_decoy_beacon_access")
    denied = evaluate_sensitive_sink(
        containment=registry,
        process_identity=state.process_identity,
        operation="protected_read",
        expected_revision=old_revision,
    )
    assert not denied.allowed
    assert "containment_revision_stale" in denied.reasons


def test_missing_process_state_fails_closed_for_sensitive_sink():
    decision = evaluate_sensitive_sink(
        containment=LiveContainmentRegistry(),
        process_identity="unregistered-process",
        operation="protected_read",
    )
    assert not decision.allowed
    assert "live_containment_state_missing" in decision.reasons


def test_unrelated_process_is_not_revoked_by_other_process_contradiction():
    registry, first = _registry("p1")
    second = registry.register("p2")
    registry.contest(first.process_identity, "unexpected_decoy_beacon_access")
    allowed = evaluate_sensitive_sink(
        containment=registry,
        process_identity=second.process_identity,
        operation="protected_read",
        expected_revision=second.revision,
    )
    assert allowed.allowed


def test_independent_clearance_does_not_restore_sensitive_authority():
    registry, state = _registry()
    registry.contest(state.process_identity, "unexpected_decoy_beacon_access")
    ok, _ = state.clear_after_independent_investigation(cleared=True, evidence_ref="audit:independent-1")
    assert ok
    assert state.authority_state == "RESTRICTED"
    assert not state.protected_data_export_allowed
    assert not state.protected_key_release_allowed
    assert not evaluate_sensitive_sink(
        containment=registry,
        process_identity=state.process_identity,
        operation="network_export",
    ).allowed


def test_export_actuator_is_not_invoked_after_containment_revocation():
    registry, state = _registry()
    calls = []
    registry.contest(state.process_identity, "unexpected_decoy_beacon_access")
    result = execute_protected_export(
        containment=registry,
        process_identity=state.process_identity,
        channel="network",
        destination="network:approved.example",
        payload=b"secret",
        authorization_verified=True,
        actuator=lambda destination, payload: calls.append((destination, payload)),
    )
    assert not result.ok
    assert not result.actuator_invoked
    assert calls == []


def test_export_actuator_requires_independent_authorization_even_when_containment_active():
    registry, state = _registry()
    calls = []
    result = execute_protected_export(
        containment=registry,
        process_identity=state.process_identity,
        channel="network",
        destination="network:approved.example",
        payload=b"secret",
        authorization_verified=False,
        actuator=lambda destination, payload: calls.append((destination, payload)),
    )
    assert not result.ok
    assert calls == []


def test_broker_response_defaults_fail_closed_without_broker_containment_proof():
    response = BrokerDecryptResponse(
        ok=True,
        status="ok",
        plaintext=b"x",
        broker_id="b",
        key_id="k",
        data_id="d",
        content_revision="r",
        operation="read",
    )
    assert not response.containment_enforced_by_broker
    assert response.containment_revision == 0


def test_sink_promotion_blocks_software_only_claim():
    decision = evaluate_sink_enforcement_promotion(SinkEnforcementEvidence(
        protected_read_rechecks_live_containment=True,
        broker_key_release_rechecks_live_containment=True,
        protected_export_rechecks_live_containment=True,
        export_actuator_rechecks_live_containment=True,
        containment_revision_enforced=True,
        missing_process_state_fails_closed=True,
        independent_clearance_does_not_restore_sensitive_authority=True,
        path_logic_final_authority=False,
        real_kernel_or_broker_enforcement_demonstrated=False,
        evidence_provenance=("v28-software-pressure",),
    ))
    assert not decision.promote
    assert "real_runtime_enforcement_not_demonstrated" in decision.reasons


def test_static_sink_audit_catches_required_bindings():
    report = audit_sink_enforcement(".")
    assert report.passed, report.reasons


def test_path_logic_remains_non_authoritative_at_sink():
    inv = sink_enforcement_invariants()
    assert inv["path_logic_final_authority"] is False
    assert inv["containment_can_only_shrink_not_grant_authority"] is True
