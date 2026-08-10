from zero_os.zero_ai_llm import MockBackend
from zero_os.zero_ai_reasoning import reason


def test_llm_reasoning_has_no_authority_without_independent_evidence():
    out = reason(
        "diagnose failure",
        requested_scope=["mechanism"],
        backend=MockBackend(),
    )
    assert out["proposal"]["authority"] == 0.0
    assert out["authority"]["status"] == "contested"
    assert out["authority"]["authority"] == 0.0
    assert out["separation"]["mutation_performed"] is False


def test_llm_can_request_scope_but_independent_evidence_certifies_it():
    evidence = [
        {
            "source": "formal_audit",
            "supports": True,
            "independent_group": "formal",
            "quality": 0.9,
            "scope": ["mechanism"],
        },
        {
            "source": "empirical_probe",
            "supports": True,
            "independent_group": "empirical",
            "quality": 0.8,
            "scope": ["mechanism"],
        },
    ]
    out = reason(
        "diagnose failure",
        requested_scope=["mechanism"],
        independent_evidence=evidence,
        backend=MockBackend(),
    )
    assert out["proposal"]["authority"] == 0.0
    assert out["authority"]["status"] == "provisional"
    assert out["authority"]["authority"] == 0.8
    assert out["authority"]["demonstrated_scope"] == ["mechanism"]
