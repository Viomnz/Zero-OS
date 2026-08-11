from __future__ import annotations

from zero_os.pure_logic_authority_kernel import ConstitutionalRequest, IdentityAuthority


def _request(**overrides):
    data = {
        "actor": IdentityAuthority(
            principal_id="zero-ai",
            provenance=("autonomous_controller",),
            authenticated=True,
            demonstrated_scopes=frozenset({"runtime:self_repair"}),
        ),
        "action_scope": "runtime:self_repair",
        "objective_id": "runtime-health",
        "authority_id": "repair-authority",
        "requested_capability": "self_repair",
        "consequence": "high",
        "reversible": True,
        "controller_id": "self_repair",
        "controller_eligible": False,
        "controller_loop_state": "",
        "controller_authority_state": "",
        "controller_scope": (),
    }
    data.update(overrides)
    return ConstitutionalRequest(**data)


def test_autonomous_request_defaults_fail_closed_without_controller_evidence():
    request = _request()
    assert request.requested_capability == "self_repair"
    assert request.controller_eligible is False


def test_autonomous_request_can_carry_only_eligibility_not_final_authority():
    request = _request(
        controller_eligible=True,
        controller_loop_state="READY",
        controller_authority_state="PROVISIONAL",
        controller_scope=("runtime:self_repair",),
    )
    assert request.controller_eligible is True
    assert not hasattr(request, "execution_authority_granted")
    assert not hasattr(request, "promotion_permitted")


def test_controller_scope_must_be_explicit():
    request = _request(controller_eligible=True, controller_loop_state="READY", controller_authority_state="PROVISIONAL")
    assert "runtime:self_repair" not in request.controller_scope
