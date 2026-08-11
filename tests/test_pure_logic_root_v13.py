from __future__ import annotations

import json
from pathlib import Path

from zero_os.authority_state_machine import AuthorityArtifactState, check_transition
from zero_os.external_authority_issuer import assess_external_issuer, descriptor_path, external_issuer_status
from zero_os.formal_authority_model_check import model_check_authority_state_machine


def test_illegal_authority_jump_is_denied():
    decision = check_transition(AuthorityArtifactState.PROPOSED, AuthorityArtifactState.ACTIVE)
    assert decision.allowed is False


def test_terminal_revoked_authority_cannot_revive():
    decision = check_transition(AuthorityArtifactState.REVOKED, AuthorityArtifactState.ACTIVE)
    assert decision.allowed is False


def test_finite_state_model_rejects_forbidden_edges():
    result = model_check_authority_state_machine()
    assert result["ok"] is True
    assert result["forbidden_edges_accepted"] == []
    assert result["terminal_revival_edges"] == []


def test_missing_external_issuer_is_not_production_ready(tmp_path: Path):
    status = assess_external_issuer(str(tmp_path))
    assert status.production_authority_permitted is False
    assert status.private_key_exposed_to_runtime is True


def test_external_issuer_requires_real_separation_claims(tmp_path: Path):
    path = descriptor_path(str(tmp_path))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "issuer_id": "issuer-test",
        "transport": "local-ipc",
        "endpoint": "/run/zero-os/issuer.sock",
        "public_key_path": "/etc/zero-os/issuer.pub",
        "separate_process": True,
        "separate_os_identity": False,
        "hardware_backed": False,
        "private_key_unavailable_to_runtime": True,
    }), encoding="utf-8")
    status = external_issuer_status(str(tmp_path))
    assert status["configured"] is True
    assert status["boundary"]["production_authority_permitted"] is False


def test_os_protected_external_issuer_can_satisfy_boundary_contract(tmp_path: Path):
    path = descriptor_path(str(tmp_path))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "issuer_id": "issuer-test",
        "transport": "local-ipc",
        "endpoint": "/run/zero-os/issuer.sock",
        "public_key_path": "/etc/zero-os/issuer.pub",
        "separate_process": True,
        "separate_os_identity": True,
        "hardware_backed": False,
        "private_key_unavailable_to_runtime": True,
    }), encoding="utf-8")
    status = external_issuer_status(str(tmp_path))
    assert status["boundary"]["production_authority_permitted"] is True
