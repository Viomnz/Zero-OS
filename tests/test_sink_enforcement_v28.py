from zero_os.containment_sink_enforcement import evaluate_sensitive_sink, sink_enforcement_invariants
from zero_os.live_containment_state import LiveContainmentRegistry
from zero_os.process_identity_evidence import KernelProcessIdentityEvidence
from zero_os.protected_data_broker_runtime import BrokerDecryptResponse
from zero_os.protected_export_sinks import ExportAuthorizationEvidence, execute_protected_export
from zero_os.sink_enforcement_audit import audit_sink_enforcement
from zero_os.sink_enforcement_promotion import SinkEnforcementEvidence, evaluate_sink_enforcement_promotion


def _evidence(*, pid=4242, start=123, executable_hash="abc"):
    return KernelProcessIdentityEvidence(
        pid=pid,
        process_start_time_ns=start,
        executable_hash=executable_hash,
        uid=1000,
        gid=1000,
        source="test-kernel",
        source_event_id=f"proc-{pid}-{start}-{executable_hash}",
        source_authenticated=True,
        kernel_origin_verified=True,
    )


def _registry(*, pid=4242, start=123, executable_hash="abc"):
    registry = LiveContainmentRegistry()
    state = registry.register_kernel_evidence(_evidence(pid=pid, start=start, executable_hash=executable_hash))
    return registry, state


def _register(registry, *, pid, start=123, executable_hash="abc"):
    return registry.register_kernel_evidence(_evidence(pid=pid, start=start, executable_hash=executable_hash))


def _export_authorization(state, *, channel="network", destination="network:approved.example", verified=True):
    return ExportAuthorizationEvidence(
        verified=verified,
        status="DATA_FLOW_VERIFIED_IN_SCOPE" if verified else "DATA_FLOW_DENIED",
        channel=channel,
        destination=destination,
        process_identity=state.process_identity,
        data_id="secret-1",
        authority_artifact_id="grant-1",
        containment_revision=state.revision,
        evidence_kind="protected_data_flow_verdict",
        authority_granted=False,
    )


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


def test_plain_string_registration_cannot_mint_clean_process_identity():
    registry = LiveContainmentRegistry()
    state = registry.register("forged-clean-name")
    assert state.authority_state == "UNVERIFIED"
    assert not state.identity_verified
    decision = evaluate_sensitive_sink(
        containment=registry,
        process_identity=state.process_identity,
        operation="protected_read",
    )
    assert not decision.allowed
    assert "process_identity_not_kernel_bound" in decision.reasons
    assert "process_authority_unverified" in decision.reasons


def test_unrelated_verified_process_is_not_revoked_by_other_process_contradiction():
    registry, first = _registry(pid=1001)
    second = _register(registry, pid=1002)
    registry.contest(first.process_identity, "unexpected_decoy_beacon_access")
    allowed = evaluate_sensitive_sink(
        containment=registry,
        process_identity=second.process_identity,
        operation="protected_read",
        expected_revision=second.revision,
    )
    assert allowed.allowed


def test_identity_reverification_cannot_clear_existing_contradiction():
    registry, state = _registry()
    registry.contest(state.process_identity, "unexpected_decoy_beacon_access")
    state = registry.register_kernel_evidence(_evidence())
    assert state.identity_verified
    assert state.authority_state == "CONTESTED"
    assert not state.protected_data_export_allowed
    assert not state.protected_key_release_allowed


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
    authorization = _export_authorization(state)
    registry.contest(state.process_identity, "unexpected_decoy_beacon_access")
    result = execute_protected_export(
        containment=registry,
        process_identity=state.process_identity,
        channel="network",
        destination="network:approved.example",
        payload=b"secret",
        authorization=authorization,
        actuator=lambda destination, payload: calls.append((destination, payload)),
    )
    assert not result.ok
    assert not result.actuator_invoked
    assert calls == []


def test_export_actuator_requires_bound_authorization_evidence():
    registry, state = _registry()
    calls = []
    result = execute_protected_export(
        containment=registry,
        process_identity=state.process_identity,
        channel="network",
        destination="network:approved.example",
        payload=b"secret",
        authorization=_export_authorization(state, verified=False),
        actuator=lambda destination, payload: calls.append((destination, payload)),
    )
    assert not result.ok
    assert result.status == "EXPORT_SINK_DENIED_AUTHORITY_INVALID"
    assert calls == []


def test_export_authorization_cannot_be_reused_for_another_destination():
    registry, state = _registry()
    calls = []
    result = execute_protected_export(
        containment=registry,
        process_identity=state.process_identity,
        channel="network",
        destination="network:evil.example",
        payload=b"secret",
        authorization=_export_authorization(state, destination="network:approved.example"),
        actuator=lambda destination, payload: calls.append((destination, payload)),
    )
    assert not result.ok
    assert calls == []


def test_export_authorization_cannot_be_reused_by_another_process():
    registry, first = _registry(pid=1001)
    second = _register(registry, pid=1002)
    calls = []
    result = execute_protected_export(
        containment=registry,
        process_identity=second.process_identity,
        channel="network",
        destination="network:approved.example",
        payload=b"secret",
        authorization=_export_authorization(first),
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
        process_identity_kernel_bound=True,
        real_kernel_or_broker_enforcement_demonstrated=False,
        evidence_provenance=("v28-software-pressure",),
    ))
    assert not decision.promote
    assert "real_runtime_enforcement_not_demonstrated" in decision.reasons


def test_sink_promotion_blocks_unbound_process_identity_even_with_other_evidence():
    decision = evaluate_sink_enforcement_promotion(SinkEnforcementEvidence(
        protected_read_rechecks_live_containment=True,
        broker_key_release_rechecks_live_containment=True,
        protected_export_rechecks_live_containment=True,
        export_actuator_rechecks_live_containment=True,
        containment_revision_enforced=True,
        missing_process_state_fails_closed=True,
        independent_clearance_does_not_restore_sensitive_authority=True,
        path_logic_final_authority=False,
        process_identity_kernel_bound=False,
        real_kernel_or_broker_enforcement_demonstrated=True,
        evidence_provenance=("identity-pressure",),
    ))
    assert not decision.promote
    assert "process_identity_not_kernel_bound" in decision.reasons


def test_static_sink_audit_catches_required_bindings():
    report = audit_sink_enforcement(".")
    assert report.passed, report.reasons


def test_path_logic_remains_non_authoritative_at_sink():
    inv = sink_enforcement_invariants()
    assert inv["path_logic_final_authority"] is False
    assert inv["containment_can_only_shrink_not_grant_authority"] is True
    assert inv["unverified_process_identity_fails_closed"] is True
