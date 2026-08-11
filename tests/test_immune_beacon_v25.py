from datetime import datetime, timedelta, timezone

from zero_os.immune_beacon import (
    BeaconAuthorityState,
    ImmuneBeacon,
    PressureEvidence,
    downgrade_on_contradiction,
    evaluate_beacon,
    revoke_beacon,
)
from zero_os.immune_beacon_gate import evaluate_survival_gate, gate_invariant_report


def _beacon(**overrides):
    now = datetime.now(timezone.utc)
    base = dict(
        beacon_id="beacon-1",
        subject_id="artifact-1",
        subject_kind="file",
        artifact_hash="abc123",
        state_revision="r1",
        tested_scope=("filesystem:read", "runtime:execute"),
        pressure_families=("malformed_input", "privilege_boundary"),
        max_pressure_level=4,
        evidence=(
            PressureEvidence("e1", "malformed_input", 4, "fuzz", "lineage-a", "eval-a", "PASS", ("run:a",)),
            PressureEvidence("e2", "privilege_boundary", 4, "symbolic", "lineage-b", "eval-b", "PASS", ("run:b",)),
        ),
        assumptions=("linux",),
        contradictions=(),
        revocation_triggers=("new_exploit", "parent_revoked"),
        parent_authority_ids=("parent-1",),
        issued_at_utc=now.isoformat(),
        expires_at_utc=(now + timedelta(minutes=5)).isoformat(),
        authority_state=BeaconAuthorityState.SURVIVED_IN_SCOPE,
        issuer_id="beacon-issuer",
        scope_certifier_id="scope-certifier",
    )
    base.update(overrides)
    return ImmuneBeacon(**base)


def test_valid_beacon_only_continues_authority_evaluation():
    result = evaluate_survival_gate(
        beacon=_beacon(),
        current_artifact_hash="abc123",
        current_state_revision="r1",
        requested_scope=("filesystem:read",),
        active_parent_authority_ids=("parent-1",),
        minimum_pressure_level=3,
        minimum_independent_groups=2,
    )
    assert result.continue_authority_evaluation is True
    assert result.final_authority_granted is False


def test_artifact_change_invalidates_old_beacon():
    result = evaluate_beacon(
        _beacon(),
        current_artifact_hash="changed",
        current_state_revision="r1",
        requested_scope=("filesystem:read",),
        active_parent_authority_ids=("parent-1",),
    )
    assert not result.valid_for_requested_scope
    assert "beacon_artifact_hash_mismatch" in result.reasons


def test_revision_change_invalidates_old_beacon():
    result = evaluate_beacon(
        _beacon(),
        current_artifact_hash="abc123",
        current_state_revision="r2",
        requested_scope=("filesystem:read",),
        active_parent_authority_ids=("parent-1",),
    )
    assert not result.valid_for_requested_scope
    assert "beacon_state_revision_mismatch" in result.reasons


def test_scope_cannot_expand_from_prior_survival():
    result = evaluate_beacon(
        _beacon(),
        current_artifact_hash="abc123",
        current_state_revision="r1",
        requested_scope=("credential:read",),
        active_parent_authority_ids=("parent-1",),
    )
    assert not result.valid_for_requested_scope
    assert any(x.startswith("beacon_scope_not_demonstrated") for x in result.reasons)


def test_dependent_evidence_does_not_fake_independence():
    evidence = (
        PressureEvidence("e1", "malformed_input", 4, "fuzz", "same-lineage", "eval-a", "PASS"),
        PressureEvidence("e2", "privilege_boundary", 4, "fuzz", "same-lineage", "eval-b", "PASS"),
    )
    result = evaluate_beacon(
        _beacon(evidence=evidence),
        current_artifact_hash="abc123",
        current_state_revision="r1",
        requested_scope=("filesystem:read",),
        active_parent_authority_ids=("parent-1",),
        minimum_independent_groups=2,
    )
    assert not result.valid_for_requested_scope
    assert "beacon_independent_evidence_insufficient" in result.reasons


def test_parent_revocation_contests_beacon():
    result = evaluate_beacon(
        _beacon(),
        current_artifact_hash="abc123",
        current_state_revision="r1",
        requested_scope=("filesystem:read",),
        active_parent_authority_ids=(),
    )
    assert not result.valid_for_requested_scope
    assert any(x.startswith("beacon_parent_authority_missing") for x in result.reasons)


def test_new_contradiction_contests_and_downgrades():
    beacon = downgrade_on_contradiction(_beacon(), "runtime_failure")
    assert beacon.authority_state is BeaconAuthorityState.CONTESTED
    result = evaluate_beacon(
        beacon,
        current_artifact_hash="abc123",
        current_state_revision="r1",
        requested_scope=("filesystem:read",),
        active_parent_authority_ids=("parent-1",),
    )
    assert not result.valid_for_requested_scope


def test_revocation_trigger_revokes_transfer():
    result = evaluate_beacon(
        _beacon(),
        current_artifact_hash="abc123",
        current_state_revision="r1",
        requested_scope=("filesystem:read",),
        active_parent_authority_ids=("parent-1",),
        triggered_revocations=("new_exploit",),
    )
    assert not result.valid_for_requested_scope
    assert any(x.startswith("beacon_revocation_triggered") for x in result.reasons)


def test_self_certification_is_forbidden():
    result = evaluate_beacon(
        _beacon(issuer_id="artifact-1", scope_certifier_id="artifact-1"),
        current_artifact_hash="abc123",
        current_state_revision="r1",
        requested_scope=("filesystem:read",),
        active_parent_authority_ids=("parent-1",),
    )
    assert not result.valid_for_requested_scope
    assert "beacon_subject_cannot_self_issue" in result.reasons
    assert "beacon_subject_cannot_self_certify_scope" in result.reasons


def test_expired_beacon_does_not_mean_trusted_forever():
    past = datetime.now(timezone.utc) - timedelta(seconds=1)
    result = evaluate_beacon(
        _beacon(expires_at_utc=past.isoformat()),
        current_artifact_hash="abc123",
        current_state_revision="r1",
        requested_scope=("filesystem:read",),
        active_parent_authority_ids=("parent-1",),
    )
    assert not result.valid_for_requested_scope
    assert "beacon_expired" in result.reasons


def test_revoked_beacon_stays_non_authoritative():
    beacon = revoke_beacon(_beacon(), "critical_failure")
    result = evaluate_beacon(
        beacon,
        current_artifact_hash="abc123",
        current_state_revision="r1",
        requested_scope=("filesystem:read",),
        active_parent_authority_ids=("parent-1",),
    )
    assert not result.valid_for_requested_scope
    assert result.final_authority_granted is False


def test_gate_invariants_forbid_beacon_sovereignty():
    report = gate_invariant_report()
    assert report["beacon_is_final_authority"] is False
    assert report["beacon_may_mint_capability"] is False
    assert report["beacon_may_expand_scope"] is False
    assert report["beacon_may_self_renew"] is False
