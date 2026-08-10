from zero_os.pure_logic_authority import (
    AUTHORITY_CONTESTED,
    AUTHORITY_PROVISIONAL,
    Evidence,
    certify_scope,
)


def test_proposer_cannot_self_certify_scope():
    decision = certify_scope(
        {"mechanism", "safety"},
        [Evidence("discovery", True, "discovery", 1.0, frozenset({"mechanism", "safety"}))],
        proposer_source="discovery",
    )
    assert decision.status == AUTHORITY_CONTESTED
    assert decision.authority == 0.0


def test_one_independent_family_is_not_enough():
    decision = certify_scope(
        {"mechanism"},
        [
            Evidence("audit_a", True, "same_family", 0.99, frozenset({"mechanism"})),
            Evidence("audit_b", True, "same_family", 0.99, frozenset({"mechanism"})),
        ],
        proposer_source="discovery",
    )
    assert decision.status == AUTHORITY_CONTESTED
    assert "insufficient_independent_groups" in decision.reasons


def test_scope_cannot_expand_beyond_evidence():
    decision = certify_scope(
        {"mechanism", "safety"},
        [
            Evidence("audit_a", True, "formal", 0.9, frozenset({"mechanism"})),
            Evidence("audit_b", True, "empirical", 0.8, frozenset({"mechanism"})),
        ],
        proposer_source="discovery",
    )
    assert decision.status == AUTHORITY_CONTESTED
    assert decision.demonstrated_scope == frozenset({"mechanism"})
    assert decision.authority == 0.0


def test_independent_contradiction_blocks_authority():
    decision = certify_scope(
        {"mechanism"},
        [
            Evidence("audit_a", True, "formal", 0.9, frozenset({"mechanism"})),
            Evidence("audit_b", True, "empirical", 0.9, frozenset({"mechanism"})),
            Evidence("red_team", False, "adversarial", 0.7, frozenset({"mechanism"})),
        ],
        proposer_source="discovery",
    )
    assert decision.status == AUTHORITY_CONTESTED
    assert "independent_contradiction_present" in decision.reasons


def test_two_independent_groups_can_grant_only_provisional_authority():
    decision = certify_scope(
        {"mechanism"},
        [
            Evidence("audit_a", True, "formal", 0.91, frozenset({"mechanism"})),
            Evidence("audit_b", True, "empirical", 0.84, frozenset({"mechanism"})),
        ],
        proposer_source="discovery",
    )
    assert decision.status == AUTHORITY_PROVISIONAL
    assert decision.authority == 0.84
    assert "authority_is_provisional_and_revocable" in decision.reasons
