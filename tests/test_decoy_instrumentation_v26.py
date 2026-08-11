from zero_os.decoy_authority_bridge import bridge_invariants, evaluate_decoy_authority_effect
from zero_os.decoy_beacon import DecoyBeacon, DecoyBeaconState
from zero_os.decoy_event_ingest import DecoyAccessKind, DecoyKernelEvent, ingest_decoy_event, instrumentation_invariants
from zero_os.decoy_instrumentation_promotion import evaluate_decoy_instrumentation_promotion


EXPECTED_PROCESS = f"4242:123456789:{'a' * 64}"


def _beacon(*, expected_processes=()) -> DecoyBeacon:
    return DecoyBeacon(
        beacon_id="decoy-1",
        decoy_kind="fake-root-manifest",
        apparent_role="root-authority-backup",
        protected_location="/var/lib/zero-os/decoys/root-authority.json",
        expected_accessors=("zero-os-decoy-maintenance",),
        expected_process_identities=tuple(expected_processes),
        created_at="2026-08-10T20:00:00+00:00",
        expires_at="2027-08-10T20:00:00+00:00",
        evidence_sink="authority-ledger",
        response_policy="contest-and-investigate",
        state=DecoyBeaconState.ARMED,
    )


def _event(actor: str = "unknown", *, provenance: bool = True, path: str | None = None, seq: int = 7) -> DecoyKernelEvent:
    return DecoyKernelEvent(
        beacon_id="decoy-1",
        actor_id=actor,
        process_id="4242",
        process_start_time_ns=123456789,
        executable_hash="a" * 64,
        uid=1000,
        gid=1000,
        access_kind=DecoyAccessKind.READ,
        object_path=path or "/var/lib/zero-os/decoys/root-authority.json",
        observed_at="2026-08-10T20:10:00+00:00",
        source="linux-audit",
        source_event_id="audit:9001",
        kernel_audit_sequence=seq,
        provenance_verified=provenance,
    )


def test_valid_kernel_event_becomes_evidence_only():
    result = ingest_decoy_event(_beacon(), _event())
    assert result.accepted
    assert result.touch is not None
    assert not result.authority_granted
    assert not result.final_malicious_judgment
    assert result.touch.process_id == EXPECTED_PROCESS


def test_unverified_or_misbound_event_is_rejected():
    assert not ingest_decoy_event(_beacon(), _event(provenance=False)).accepted
    assert not ingest_decoy_event(_beacon(), _event(path="/tmp/not-the-decoy")).accepted
    assert not ingest_decoy_event(_beacon(), _event(seq=0)).accepted


def test_unexpected_touch_requests_authority_shrink_not_guilt():
    ingest, response, effect = evaluate_decoy_authority_effect(_beacon(), _event())
    assert ingest.accepted
    assert response is not None
    assert effect.contest_process_authority
    assert effect.revoke_sensitive_export
    assert effect.reduce_key_release_eligibility
    assert effect.require_investigation
    assert not effect.final_malicious_judgment
    assert not effect.authority_granted


def test_exact_process_identity_maintenance_touch_does_not_shrink_authority():
    _, _, effect = evaluate_decoy_authority_effect(
        _beacon(expected_processes=(EXPECTED_PROCESS,)),
        _event("zero-os-decoy-maintenance"),
    )
    assert not effect.contest_process_authority
    assert not effect.revoke_sensitive_export
    assert not effect.reduce_key_release_eligibility


def test_friendly_actor_label_without_process_binding_still_shrinks_authority():
    _, _, effect = evaluate_decoy_authority_effect(_beacon(), _event("zero-os-decoy-maintenance"))
    assert effect.contest_process_authority
    assert effect.revoke_sensitive_export
    assert effect.reduce_key_release_eligibility


def test_promotion_requires_real_runtime_tripwire_evidence():
    blocked = evaluate_decoy_instrumentation_promotion(
        instrumentation_report=instrumentation_invariants(),
        authority_bridge_report=bridge_invariants(),
        runtime_tripwire_report=None,
    )
    assert not blocked.promote
    good_runtime = {
        "file_stat_instrumented": True,
        "file_open_instrumented": True,
        "file_read_instrumented": True,
        "process_identity_provenance_verified": True,
        "event_replay_detected": True,
        "expected_process_identities_suppressed": True,
        "unexpected_touch_reaches_authority_shrink_path": True,
        "final_malicious_judgment": False,
        "authority_granted": False,
    }
    passed = evaluate_decoy_instrumentation_promotion(
        instrumentation_report=instrumentation_invariants(),
        authority_bridge_report=bridge_invariants(),
        runtime_tripwire_report=good_runtime,
    )
    assert passed.promote
