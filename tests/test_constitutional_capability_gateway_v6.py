from datetime import datetime, timedelta, timezone

from zero_os.capability_execution_gateway import authorized_capability_context, gate_action


def _future(seconds=120):
    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat()


def _plan(scope="network:fetch", kind="web_fetch"):
    return {
        "capability_context": {
            "principal_id": "agent-a",
            "identity_verified": True,
            "granted_scopes": [scope, "host:example.com"],
            "permitted_hosts": ["example.com"],
            "evidence_fresh": True,
        },
        "constitutional_context": {
            "actor": {
                "principal_id": "agent-a",
                "provenance": ["local_session"],
                "authenticated": True,
                "demonstrated_scopes": [scope],
                "trust_state": "NORMAL",
            },
            "authority_id": "claim-net",
            "objective_id": "obj-net",
            "authority_records": [
                {
                    "authority_id": "claim-net",
                    "subject_id": "network-operation",
                    "claim_type": "capability_authority",
                    "value_fingerprint": "opaque-for-capability-gate",
                    "state_revision": "r1",
                    "demonstrated_scope": [scope],
                    "state": "SURVIVED_IN_SCOPE",
                    "expires_at_utc": _future(),
                }
            ],
            "objective_records": [
                {
                    "objective_id": "obj-net",
                    "statement": "retrieve explicitly requested resource",
                    "provenance": ["user_request"],
                    "demonstrated_scope": [scope],
                    "status": "SURVIVED_IN_SCOPE",
                    "expires_at_utc": _future(),
                }
            ],
            "active_dependency_ids": [],
            "reversible": True,
            "legal_state_ok": True,
            "correction_plane_allows": True,
        },
    }


def test_sensitive_read_is_denied_without_constitutional_context(tmp_path):
    plan = _plan()
    plan.pop("constitutional_context")
    gate = gate_action(str(tmp_path), "web_fetch", plan_context=plan)
    assert gate["allowed"] is False
    assert gate["reason"] == "constitutional_context_missing"


def test_sensitive_read_survives_capability_and_constitutional_authority(tmp_path):
    gate = gate_action(str(tmp_path), "web_fetch", plan_context=_plan())
    assert gate["allowed"] is True
    assert gate["constitutional"].allowed is True


def test_revoked_objective_blocks_sensitive_read_lease(tmp_path):
    plan = _plan()
    plan["constitutional_context"]["objective_records"][0]["status"] = "REVOKED"
    gate = gate_action(str(tmp_path), "web_fetch", plan_context=plan)
    assert gate["allowed"] is False
    assert gate["constitutional"].allowed is False


def test_host_scope_is_not_invented_by_lease_issuer(tmp_path):
    plan = _plan()
    plan["capability_context"]["granted_scopes"] = ["network:fetch"]
    with authorized_capability_context(str(tmp_path), "web_fetch", plan_context=plan) as gate:
        assert gate["allowed"] is True
        assert "host:example.com" not in set(gate["lease"]["scopes"])


def test_host_scope_is_delegated_only_when_already_granted(tmp_path):
    with authorized_capability_context(str(tmp_path), "web_fetch", plan_context=_plan()) as gate:
        assert gate["allowed"] is True
        assert "host:example.com" in set(gate["lease"]["scopes"])
