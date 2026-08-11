from zero_os.security_control_plane import control_key, load_state, mutate_state, verify_history_chain
from zero_os.security_signing import sign_antivirus_feed, verify_antivirus_feed


def test_security_control_mutation_fails_without_constitutional_handoff(tmp_path):
    result = mutate_state(str(tmp_path), "set_antivirus_policy", {"key": "response_mode", "value": "manual"})
    assert result["ok"] is False
    assert result["reason"] == "security_control_plane_authority_missing"


def test_security_control_key_is_random_not_path_derived(tmp_path):
    first = control_key(str(tmp_path), "antivirus_feed")
    second_root = tmp_path / "other"
    second = control_key(str(second_root), "antivirus_feed")
    assert len(first) == 32
    assert len(second) == 32
    assert first != second


def test_signed_feed_detects_tamper_and_rollback(tmp_path):
    feed = {"version": 7, "signatures": [{"id": "X", "kind": "contains", "value": "x"}]}
    envelope = sign_antivirus_feed(str(tmp_path), feed)
    assert verify_antivirus_feed(str(tmp_path), envelope, minimum_version=7)["ok"] is True

    tampered = dict(envelope)
    tampered["feed"] = {"version": 7, "signatures": []}
    assert verify_antivirus_feed(str(tmp_path), tampered, minimum_version=7)["ok"] is False

    assert verify_antivirus_feed(str(tmp_path), envelope, minimum_version=8)["reason"] == "feed_rollback_detected"


def test_initial_control_state_has_chain_status(tmp_path):
    state = load_state(str(tmp_path))
    assert state.revision == 1
    result = verify_history_chain(str(tmp_path))
    assert result["ok"] is True
