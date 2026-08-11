from zero_os.capability_lease import issue_capability_lease
from zero_os.execution_authority_ticket import issue_execution_ticket


def test_arbitrary_code_must_not_be_able_to_mint_capability_lease(tmp_path):
    try:
        lease = issue_capability_lease("attacker", {"credential:read"})
    except PermissionError:
        return
    assert lease is None, "arbitrary caller minted an accepted capability lease"


def test_arbitrary_code_must_not_be_able_to_mint_execution_ticket(tmp_path):
    try:
        ticket = issue_execution_ticket(
            str(tmp_path),
            action_kind="self_upgrade",
            authority_id="forged",
            subject_id="forged",
            required_scope="zero_os:self_upgrade",
            state_revision="r-forged",
        )
    except PermissionError:
        return
    assert ticket is None, "arbitrary caller minted an accepted execution ticket"
