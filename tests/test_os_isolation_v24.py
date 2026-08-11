from zero_os.linux_broker_profile import LinuxBrokerProfile, compare_systemd_properties
from zero_os.os_isolation import IsolationState, OSIsolationEvidence, evaluate_os_isolation
from zero_os.tpm_sealed_key_policy import TPMSealedKeyPolicy, TPMUnsealEvidence, evaluate_tpm_unseal


def _good_os() -> OSIsolationEvidence:
    return OSIsolationEvidence(
        state=IsolationState.OS_ENFORCED,
        runtime_uid="zero-os-runtime",
        broker_uid="zero-os-broker",
        distinct_uids=True,
        protected_store_owner_is_broker=True,
        protected_store_mode_blocks_runtime=True,
        broker_socket_peer_credentials_verified=True,
        broker_service_no_new_privileges=True,
        broker_private_tmp=True,
        broker_protect_system_strict=True,
        broker_protect_home=True,
        runtime_ptrace_broker_blocked=True,
        broker_memory_dump_blocked=True,
        runtime_namespace_cannot_mount_protected_store=True,
        runtime_cannot_open_cipher_key_store=True,
        network_egress_default_deny_for_broker=True,
        evidence_provenance=("systemd-show", "proc-status", "namespace-pressure"),
    )


def test_os_isolation_survives_complete_evidence():
    result = evaluate_os_isolation(_good_os())
    assert result.isolated
    assert result.authority_granted is False


def test_same_uid_fails_closed():
    item = _good_os()
    bad = OSIsolationEvidence(**{**item.__dict__, "broker_uid": item.runtime_uid, "distinct_uids": False})
    result = evaluate_os_isolation(bad)
    assert not result.isolated
    assert "runtime_and_broker_share_os_identity" in result.reasons


def test_ptrace_escape_fails_closed():
    item = _good_os()
    bad = OSIsolationEvidence(**{**item.__dict__, "runtime_ptrace_broker_blocked": False})
    result = evaluate_os_isolation(bad)
    assert not result.isolated
    assert "runtime_ptrace_escape_not_blocked" in result.reasons


def test_mount_namespace_escape_fails_closed():
    item = _good_os()
    bad = OSIsolationEvidence(**{**item.__dict__, "runtime_namespace_cannot_mount_protected_store": False})
    result = evaluate_os_isolation(bad)
    assert not result.isolated


def _policy() -> TPMSealedKeyPolicy:
    return TPMSealedKeyPolicy(
        key_id="vault-master-v1",
        expected_device_id="device-1",
        expected_pcr_digest="pcr-good",
        expected_measured_boot_root="boot-good",
        minimum_monotonic_counter=7,
        broker_identity="zero-os-broker",
    )


def _good_tpm() -> TPMUnsealEvidence:
    return TPMUnsealEvidence(
        device_id="device-1",
        pcr_digest="pcr-good",
        measured_boot_root="boot-good",
        monotonic_counter=8,
        broker_identity="zero-os-broker",
        secure_boot_enabled=True,
        debug_disabled=True,
        quote_fresh=True,
        quote_signature_verified=True,
        evidence_provenance=("tpm2-quote", "measured-boot"),
    )


def test_tpm_unseal_eligibility_does_not_release_key():
    result = evaluate_tpm_unseal(_policy(), _good_tpm())
    assert result.unseal_eligible
    assert result.key_released is False
    assert result.authority_granted is False


def test_pcr_mismatch_denies_unseal():
    item = _good_tpm()
    result = evaluate_tpm_unseal(_policy(), TPMUnsealEvidence(**{**item.__dict__, "pcr_digest": "attacker-state"}))
    assert not result.unseal_eligible


def test_stale_quote_denies_unseal():
    item = _good_tpm()
    result = evaluate_tpm_unseal(_policy(), TPMUnsealEvidence(**{**item.__dict__, "quote_fresh": False}))
    assert not result.unseal_eligible


def test_rollback_counter_denies_unseal():
    item = _good_tpm()
    result = evaluate_tpm_unseal(_policy(), TPMUnsealEvidence(**{**item.__dict__, "monotonic_counter": 6}))
    assert not result.unseal_eligible


def test_linux_profile_requires_hardening_properties():
    profile = LinuxBrokerProfile(
        runtime_user="zero-os-runtime",
        broker_user="zero-os-broker",
        protected_store="/var/lib/zero-os/protected",
        broker_socket="/run/zero-os/broker.sock",
        private_key_store="/var/lib/zero-os-broker/keys",
    )
    observed = profile.systemd_hardening_requirements()
    assert compare_systemd_properties(profile, observed)["ok"]
    bad = dict(observed)
    bad["NoNewPrivileges"] = "no"
    assert not compare_systemd_properties(profile, bad)["ok"]
