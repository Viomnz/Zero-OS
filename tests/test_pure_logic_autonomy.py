from zero_os.autonomous_fix_gate import autonomy_evaluate
from zero_os.confidence_engine import score_confidence


def _evidence(scope: str) -> list[dict]:
    return [
        {
            "source": "formal_audit",
            "supports": True,
            "independent_group": "formal",
            "quality": 0.9,
            "scope": [scope],
        },
        {
            "source": "runtime_probe",
            "supports": True,
            "independent_group": "empirical",
            "quality": 0.85,
            "scope": [scope],
        },
    ]


def test_confidence_never_grants_authority():
    result = score_confidence(
        evidence_count=100,
        contradictory_signals=0,
        historical_success_rate=1.0,
        simulation_ok=True,
        rollback_score=1.0,
        independent_verifiers=100,
    )
    assert result["confidence"] > 0.9
    assert result["heuristic_only"] is True
    assert result["grants_authority"] is False


def test_contradiction_is_explicit_even_with_high_score():
    result = score_confidence(
        evidence_count=100,
        contradictory_signals=1,
        historical_success_rate=1.0,
        simulation_ok=True,
        rollback_score=1.0,
        independent_verifiers=100,
    )
    assert result["contradiction_active"] is True
    assert result["grants_authority"] is False


def test_autonomous_mutation_without_scope_evidence_is_blocked(tmp_path):
    result = autonomy_evaluate(
        str(tmp_path),
        action="self repair run",
        blast_radius="system",
        reversible=True,
        evidence_count=100,
        contradictory_signals=0,
        independent_verifiers=100,
        checks={"dry_run": True},
        planner_confidence=0.99,
        planner_risk_level="high",
        planner_execution_mode="safe",
        authority_evidence=[],
        proposer_source="self_repair",
    )
    assert result["decision"] == "hold_for_review"
    assert result["decision_reason"] == "independent_scope_authority_missing"
    assert result["authority"]["authority"] == 0.0


def test_autonomous_gate_certifies_scope_separately_from_confidence(tmp_path):
    scope = "mutation:self repair run"
    result = autonomy_evaluate(
        str(tmp_path),
        action="self repair run",
        blast_radius="system",
        reversible=True,
        evidence_count=2,
        contradictory_signals=0,
        independent_verifiers=2,
        checks={"dry_run": True},
        planner_confidence=0.99,
        planner_risk_level="high",
        planner_execution_mode="safe",
        authority_evidence=_evidence(scope),
        proposer_source="self_repair",
    )
    assert result["authority"]["status"] == "provisional"
    assert result["authority"]["demonstrated_scope"] == [scope]
    assert result["confidence"]["grants_authority"] is False


def test_active_contradiction_blocks_even_certified_scope(tmp_path):
    scope = "mutation:self repair run"
    result = autonomy_evaluate(
        str(tmp_path),
        action="self repair run",
        blast_radius="system",
        reversible=True,
        evidence_count=2,
        contradictory_signals=1,
        independent_verifiers=2,
        checks={"dry_run": True},
        planner_confidence=0.99,
        planner_risk_level="high",
        planner_execution_mode="safe",
        authority_evidence=_evidence(scope),
        proposer_source="self_repair",
    )
    assert result["decision"] == "hold_for_review"
    assert result["decision_reason"] == "contradiction_active"
