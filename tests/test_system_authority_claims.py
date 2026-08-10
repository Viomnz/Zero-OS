from zero_os.governor_claim_gate import enforce_governor_authority
from zero_os.pure_logic_claims import CLAIM_CONTESTED, CLAIM_PROVISIONAL, certify_claim, make_claim
from zero_os.world_model_claims import claims_from_world_model


def _model():
    return {
        "ok": True,
        "time_utc": "2026-08-10T00:00:00+00:00",
        "domains": {
            "runtime": {"source": "runtime", "summary": {"runtime_ready": True, "runtime_missing": False}},
            "continuity": {"source": "continuity", "summary": {"same_system": True, "has_contradiction": False}},
            "pressure": {"source": "pressure", "summary": {"pressure_ready": True}},
            "recovery": {"source": "recovery", "summary": {"compatible_snapshot_ready": True}},
            "codebase": {"source": "codebase", "summary": {"scope_ready": True, "verification_ready": True}},
            "evolution": {"source": "evolution", "summary": {"beneficial": True}},
            "source_evolution": {"source": "source_evolution", "summary": {"beneficial": True}},
            "goals": {"source": "goals", "summary": {"current_goal_title": "repair", "current_goal_requires_user": False}},
        },
    }


def test_internal_true_boolean_is_not_authority():
    claims = claims_from_world_model(_model())
    assert claims["runtime"]["value"] is True
    assert claims["runtime"]["status"] == CLAIM_CONTESTED
    assert claims["runtime"]["authority"] == 0.0


def test_claim_requires_independent_groups():
    claim = make_claim(
        claim_id="x",
        claim_type="runtime.ready",
        value=True,
        source="runtime",
        requested_scope=["runtime:ready"],
    )
    certified = certify_claim(
        claim,
        [
            {"source": "audit_a", "supports": True, "independent_group": "formal", "quality": 0.9, "scope": ["runtime:ready"]},
            {"source": "audit_b", "supports": True, "independent_group": "empirical", "quality": 0.8, "scope": ["runtime:ready"]},
        ],
    )
    assert certified.status == CLAIM_PROVISIONAL
    assert certified.authority == 0.8


def test_high_confidence_governor_cannot_mutate_without_claim_authority():
    governed = enforce_governor_authority(
        {"call": "evolution_auto_run", "confidence": 0.99, "mode": "guarded"},
        _model(),
    )
    assert governed["proposed_call"] == "evolution_auto_run"
    assert governed["call"] == "observe"
    assert governed["authority_gate"] == "blocked"


def test_governor_can_receive_provisional_scope_authority():
    governed = enforce_governor_authority(
        {"call": "evolution_auto_run", "confidence": 0.99, "mode": "guarded"},
        _model(),
        authority_evidence={
            "evolution": [
                {"source": "formal_audit", "supports": True, "independent_group": "formal", "quality": 0.9, "scope": ["evolution:beneficial"]},
                {"source": "canary", "supports": True, "independent_group": "empirical", "quality": 0.82, "scope": ["evolution:beneficial"]},
            ]
        },
    )
    assert governed["call"] == "evolution_auto_run"
    assert governed["authority_gate"] == "provisional"


def test_evidence_for_runtime_cannot_authorize_evolution():
    governed = enforce_governor_authority(
        {"call": "evolution_auto_run", "confidence": 1.0},
        _model(),
        authority_evidence={
            "runtime": [
                {"source": "audit_a", "supports": True, "independent_group": "formal", "quality": 1.0, "scope": ["runtime:ready"]},
                {"source": "audit_b", "supports": True, "independent_group": "empirical", "quality": 1.0, "scope": ["runtime:ready"]},
            ]
        },
    )
    assert governed["call"] == "observe"
    assert governed["authority_gate"] == "blocked"
