from zero_os.decoy_beacon import DecoyBeacon, DecoyBeaconState, DecoyTouch, evaluate_decoy_touch
from zero_os.decoy_beacon_response import respond_to_decoy_touch


EXPECTED_PROCESS = "9001:123456:abc123"


def _beacon(**overrides):
    base = dict(
        beacon_id="decoy-root-manifest",
        decoy_kind="authority_manifest",
        apparent_role="root_authority_index",
        protected_location="/.zero_os/decoys/root-authority.json",
        expected_accessors=("zero-os-decoy-maintenance",),
        expected_process_identities=(),
        created_at="2026-08-10T20:00:00-07:00",
        expires_at="2026-08-20T20:00:00-07:00",
        evidence_sink="protected-contradiction-ledger",
        response_policy="contest_sensitive_capabilities",
        state=DecoyBeaconState.ARMED,
        contains_real_secret=False,
        grants_authority=False,
    )
    base.update(overrides)
    return DecoyBeacon(**base)


def _touch(**overrides):
    base = dict(
        beacon_id="decoy-root-manifest",
        actor_id="unknown-agent",
        process_id=EXPECTED_PROCESS,
        action="read",
        observed_at="2026-08-10T20:10:00-07:00",
        provenance=("kernel-file-watch", "process-identity-monitor"),
        expected_actor=False,
        accessor_binding_verified=False,
    )
    base.update(overrides)
    return DecoyTouch(**base)


def test_unexpected_touch_is_evidence_not_guilt():
    verdict, response = respond_to_decoy_touch(_beacon(), _touch())
    assert verdict.suspicious is True
    assert verdict.status == "DECOY_BEACON_TOUCHED"
    assert verdict.final_malicious_judgment is False
    assert verdict.authority_granted is False
    assert response.contest_process_authority is True
    assert response.revoke_protected_data_export is True
    assert response.require_investigation is True
    assert response.final_malicious_judgment is False


def test_exact_kernel_bound_maintenance_touch_does_not_escalate():
    touch = _touch(expected_actor=True, accessor_binding_verified=True)
    verdict, response = respond_to_decoy_touch(
        _beacon(expected_process_identities=(EXPECTED_PROCESS,)), touch
    )
    assert verdict.suspicious is False
    assert verdict.status == "EXPECTED_DECOY_ACCESS"
    assert response.contest_process_authority is False
    assert response.revoke_protected_data_export is False


def test_friendly_maintenance_label_alone_cannot_suppress_tripwire():
    touch = _touch(actor_id="zero-os-decoy-maintenance", expected_actor=True)
    verdict, response = respond_to_decoy_touch(_beacon(), touch)
    assert verdict.suspicious is True
    assert response.contest_process_authority is True


def test_decoy_with_real_secret_is_invalid():
    verdict = evaluate_decoy_touch(_beacon(contains_real_secret=True), _touch())
    assert verdict.suspicious is False
    assert verdict.status == "DECOY_EVIDENCE_INVALID"
    assert "decoy_contains_real_secret" in verdict.reasons


def test_decoy_cannot_grant_authority():
    verdict = evaluate_decoy_touch(_beacon(grants_authority=True), _touch())
    assert verdict.suspicious is False
    assert verdict.status == "DECOY_EVIDENCE_INVALID"
    assert "decoy_attempted_authority_role" in verdict.reasons
    assert verdict.authority_granted is False


def test_expired_decoy_cannot_generate_high_confidence_signal():
    beacon = _beacon(expires_at="2026-08-10T20:05:00-07:00")
    verdict = evaluate_decoy_touch(beacon, _touch(observed_at="2026-08-10T20:10:00-07:00"))
    assert verdict.suspicious is False
    assert "decoy_expired" in verdict.reasons


def test_touch_without_provenance_is_invalid():
    verdict = evaluate_decoy_touch(_beacon(), _touch(provenance=()))
    assert verdict.suspicious is False
    assert "touch_provenance_missing" in verdict.reasons
