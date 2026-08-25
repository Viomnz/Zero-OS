from zero_os.zero_ai_llm import MockBackend, propose


def test_llm_output_has_zero_authority():
    out = propose(
        "diagnose runtime instability",
        requested_scope=["runtime", "mutation:self_repair"],
        backend=MockBackend(),
    )
    assert out["authority"] == 0.0
    assert out["authority_status"] == "proposal_only"
    assert out["may_mutate"] is False
    assert out["may_self_certify"] is False


def test_llm_requested_scope_is_not_demonstrated_scope():
    out = propose(
        "find likely cause",
        requested_scope=["safety", "production"],
        backend=MockBackend(),
    )
    assert out["requested_scope"] == ["production", "safety"]
    assert "demonstrated_scope" not in out


def test_llm_preserves_unknown_and_alternatives():
    out = propose("explain failure", backend=MockBackend())
    assert "insufficient_external_evidence" in out["hypotheses"]
    assert "collect_more_evidence" in out["alternatives"]
    assert "independent_scope_certification" in out["proposed_tests"]
