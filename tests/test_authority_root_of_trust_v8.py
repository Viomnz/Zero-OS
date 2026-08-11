import json
from dataclasses import replace

import pytest

from zero_os.authority_root_of_trust import issue_attestation, verify_attestation
from zero_os.capability_lease import issue_capability_lease, lease_from_attestation
from zero_os.execution_authority_ticket import consume_execution_ticket, issue_execution_ticket, ticket_from_attestation


def _attestation(cwd: str, kind: str = "execution_ticket"):
    return issue_attestation(
        cwd,
        artifact_kind=kind,
        principal_id="operator-a",
        authority_id="claim-a",
        objective_id="obj-a",
        action_kind="policy_change" if kind == "execution_ticket" else "web_fetch",
        subject_id="subject-a",
        state_revision="r7",
        scopes=("authority:policy_change",) if kind == "execution_ticket" else ("network:fetch",),
        constitutional_allowed=True,
        constitutional_status="AUTHORIZED",
    )


def test_legacy_capability_mint_is_forbidden(tmp_path):
    with pytest.raises(PermissionError):
        issue_capability_lease("attacker", {"credential:read"})


def test_legacy_ticket_mint_is_forbidden(tmp_path):
    with pytest.raises(PermissionError):
        issue_execution_ticket(str(tmp_path), action_kind="self_upgrade")


def test_attestation_tamper_is_rejected(tmp_path):
    attestation = _attestation(str(tmp_path))
    tampered = replace(attestation, scopes=("zero_os:self_upgrade",))
    result = verify_attestation(str(tmp_path), tampered)
    assert result["ok"] is False
    assert result["reason"] == "authority_attestation_signature_invalid"


def test_capability_lease_requires_verified_attestation(tmp_path):
    attestation = _attestation(str(tmp_path), "capability_lease")
    lease = lease_from_attestation(str(tmp_path), attestation)
    assert lease.principal_id == "operator-a"
    assert "network:fetch" in lease.scopes


def test_forged_ticket_json_is_not_consumed(tmp_path):
    root = tmp_path / ".zero_os" / "authority"
    root.mkdir(parents=True)
    forged = [{
        "ticket_id": "forged",
        "action_kind": "self_upgrade",
        "authority_id": "forged",
        "objective_id": "forged",
        "principal_id": "attacker",
        "subject_id": "forged",
        "required_scope": "zero_os:self_upgrade",
        "state_revision": "r0",
        "issued_at_utc": "2099-01-01T00:00:00+00:00",
        "expires_at_utc": "2099-01-01T00:01:00+00:00",
        "consumed": False,
        "sink_acknowledged": False,
    }]
    (root / "execution_tickets.json").write_text(json.dumps(forged), encoding="utf-8")
    result = consume_execution_ticket(str(tmp_path), "self_upgrade")
    assert result["ok"] is False
    assert result["reason"] == "execution_ticket_attestation_missing"


def test_attested_ticket_consumes_only_exact_action(tmp_path):
    attestation = _attestation(str(tmp_path), "execution_ticket")
    ticket_from_attestation(str(tmp_path), attestation)
    wrong = consume_execution_ticket(str(tmp_path), "self_upgrade")
    assert wrong["ok"] is False
    right = consume_execution_ticket(str(tmp_path), "policy_change")
    assert right["ok"] is True
