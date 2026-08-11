from zero_os.decoy_beacon import DecoyBeacon
from zero_os.decoy_live_containment import process_linux_decoy_event
from zero_os.linux_decoy_event_adapter import LinuxAccessRecord, LinuxEventSource
from zero_os.live_containment_state import LiveContainmentRegistry
from zero_os.replay_resistant_event_ledger import ReplayResistantEventLedger


EXPECTED_PROCESS = "4242:123456:abc123"


def beacon(*, expected_processes=()):
    return DecoyBeacon(
        beacon_id="decoy-root-1",
        decoy_kind="file",
        apparent_role="root_authority_manifest",
        protected_location="/var/lib/zero-os/decoys/root-authority.json",
        expected_accessors=("zero-os-maintenance",),
        created_at="2026-08-10T00:00:00+00:00",
        expires_at="2026-09-10T00:00:00+00:00",
        evidence_sink="security-ledger",
        response_policy="contest-sensitive-authority",
        expected_process_identities=tuple(expected_processes),
    )


def record(*, actor="unknown", seq=1, event_id="e1", authenticated=True, kernel=True, pid=4242, start=123456, executable_hash="abc123"):
    return LinuxAccessRecord(
        source=LinuxEventSource.AUDITD,
        source_event_id=event_id,
        audit_sequence=seq,
        beacon_id="decoy-root-1",
        actor_id=actor,
        pid=pid,
        process_start_time_ns=start,
        executable_hash=executable_hash,
        uid=1000,
        gid=1000,
        action="read",
        object_path="/var/lib/zero-os/decoys/root-authority.json",
        observed_at="2026-08-10T12:00:00+00:00",
        source_authenticated=authenticated,
        kernel_origin_verified=kernel,
    )


def test_unexpected_touch_revokes_export_and_key_release():
    decision = process_linux_decoy_event(
        beacon=beacon(), record=record(),
        event_ledger=ReplayResistantEventLedger(),
        containment=LiveContainmentRegistry(),
    )
    assert decision.accepted
    assert decision.authority_state == "CONTESTED"
    assert not decision.export_allowed
    assert not decision.key_release_allowed
    assert not decision.final_malicious_judgment
    assert not decision.authority_granted


def test_exact_kernel_bound_expected_process_does_not_shrink_containment():
    decision = process_linux_decoy_event(
        beacon=beacon(expected_processes=(EXPECTED_PROCESS,)),
        record=record(actor="zero-os-maintenance"),
        event_ledger=ReplayResistantEventLedger(),
        containment=LiveContainmentRegistry(),
    )
    assert decision.accepted
    assert decision.authority_state == "ACTIVE"
    assert decision.export_allowed
    assert decision.key_release_allowed
    assert not decision.authority_granted


def test_friendly_actor_label_alone_cannot_suppress_tripwire():
    decision = process_linux_decoy_event(
        beacon=beacon(),
        record=record(actor="zero-os-maintenance"),
        event_ledger=ReplayResistantEventLedger(),
        containment=LiveContainmentRegistry(),
    )
    assert decision.accepted
    assert decision.authority_state == "CONTESTED"
    assert not decision.export_allowed
    assert not decision.key_release_allowed


def test_expected_pid_with_new_process_lifetime_is_not_allowlisted():
    decision = process_linux_decoy_event(
        beacon=beacon(expected_processes=(EXPECTED_PROCESS,)),
        record=record(actor="zero-os-maintenance", start=999999),
        event_ledger=ReplayResistantEventLedger(),
        containment=LiveContainmentRegistry(),
    )
    assert decision.accepted
    assert decision.authority_state == "CONTESTED"


def test_replay_is_rejected():
    ledger = ReplayResistantEventLedger()
    registry = LiveContainmentRegistry()
    first = process_linux_decoy_event(beacon=beacon(), record=record(), event_ledger=ledger, containment=registry)
    second = process_linux_decoy_event(beacon=beacon(), record=record(), event_ledger=ledger, containment=registry)
    assert first.accepted
    assert not second.accepted
    assert "REPLAY" in second.status


def test_unverified_kernel_origin_is_rejected():
    decision = process_linux_decoy_event(
        beacon=beacon(), record=record(kernel=False),
        event_ledger=ReplayResistantEventLedger(),
        containment=LiveContainmentRegistry(),
    )
    assert not decision.accepted


def test_unauthenticated_source_is_rejected():
    decision = process_linux_decoy_event(
        beacon=beacon(), record=record(authenticated=False),
        event_ledger=ReplayResistantEventLedger(),
        containment=LiveContainmentRegistry(),
    )
    assert not decision.accepted
