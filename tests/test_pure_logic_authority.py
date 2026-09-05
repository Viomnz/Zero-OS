from zero_os.pure_logic_authority import (
    AUTHORITY_CONTESTED,
    AUTHORITY_PROVISIONAL,
    Evidence,
    certify_candidate,
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


def test_malformed_evidence_cannot_become_positive_support():
    good = {"source": "audit_a", "supports": True, "independent_group": "a",
            "quality": 0.9, "scope": ["mutation:backup"]}
    for field, value in (("supports", "false"), ("supports", 1),
                         ("quality", float("nan")), ("quality", float("inf")),
                         ("quality", "1.0"), ("source", " "),
                         ("scope", "mutation:backup"), ("scope", [None])):
        result = certify_candidate({"source": "proposer", "scope": ["mutation:backup"]},
                                   [good, {**good, "source": "audit_b", "independent_group": "b", field: value}])
        assert result["status"] == AUTHORITY_CONTESTED, (field, value)
        assert result["authority"] == 0


def test_one_source_cannot_claim_multiple_independent_groups():
    result = certify_scope({"a"}, [Evidence("audit", True, group, 1.0, frozenset({"a"}))
                                  for group in ("x", "y")])
    assert result.status == AUTHORITY_CONTESTED
    assert "source_lineage_conflict" in result.reasons


def test_declared_proposer_family_cannot_certify_proposer():
    result = certify_scope({"a"}, [
        Evidence("proposer", True, "family", 1.0, frozenset({"a"})),
        Evidence("alias", True, "family", 1.0, frozenset({"a"})),
        Evidence("outside", True, "other", 1.0, frozenset({"a"})),
    ], proposer_source="proposer")
    assert result.status == AUTHORITY_CONTESTED


def test_split_scope_evidence_is_valid_without_scope_leakage():
    evidence = [Evidence(group, True, group, 0.8, frozenset({dimension}))
                for dimension in ("a", "b") for group in ("x", "y")]
    assert certify_scope({"a", "b"}, evidence).permits_authority
    assert not certify_scope({"a", "b", "c"}, evidence).permits_authority


def test_unrelated_contradiction_does_not_revoke_other_scope():
    evidence = [Evidence(group, True, group, 0.8, frozenset({"a"})) for group in ("x", "y")]
    evidence.append(Evidence("red", False, "red", 0.9, frozenset({"b"})))
    assert certify_scope({"a"}, evidence).permits_authority


def test_new_contradiction_revokes_previously_supported_scope():
    evidence = [Evidence(group, True, group, 0.8, frozenset({"a"})) for group in ("x", "y")]
    assert certify_scope({"a"}, evidence).permits_authority
    evidence.append(Evidence("proposer", False, "proposer", 1.0, frozenset({"a"})))
    assert not certify_scope({"a"}, evidence, proposer_source="proposer").permits_authority
