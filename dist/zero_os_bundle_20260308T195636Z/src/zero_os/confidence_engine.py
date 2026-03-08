from __future__ import annotations


def score_confidence(
    evidence_count: int,
    contradictory_signals: int,
    historical_success_rate: float,
    simulation_ok: bool,
    rollback_score: float,
    independent_verifiers: int,
) -> dict:
    evidence_score = min(0.3, max(0, int(evidence_count)) * 0.05)
    contradiction_penalty = min(0.25, max(0, int(contradictory_signals)) * 0.08)
    history_score = max(0.0, min(0.25, float(historical_success_rate) * 0.25))
    simulation_score = 0.15 if simulation_ok else 0.0
    rollback_component = max(0.0, min(0.15, float(rollback_score) * 0.15))
    verifier_score = min(0.14, max(0, int(independent_verifiers)) * 0.035)
    confidence = 0.2 + evidence_score + history_score + simulation_score + rollback_component + verifier_score - contradiction_penalty
    confidence = round(max(0.0, min(0.99, confidence)), 4)
    return {
        "confidence": confidence,
        "factors": {
            "evidence_score": round(evidence_score, 4),
            "contradiction_penalty": round(contradiction_penalty, 4),
            "history_score": round(history_score, 4),
            "simulation_score": round(simulation_score, 4),
            "rollback_score": round(rollback_component, 4),
            "verifier_score": round(verifier_score, 4),
        },
    }
