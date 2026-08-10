from __future__ import annotations

from typing import Any

from zero_os.pure_logic_claims import Claim, certify_claim, make_claim


_DOMAIN_SCOPES = {
    "runtime": "runtime:ready",
    "continuity": "continuity:same_system",
    "pressure": "pressure:survived",
    "recovery": "recovery:ready",
    "codebase": "codebase:mutation_ready",
    "evolution": "evolution:beneficial",
    "source_evolution": "source_evolution:beneficial",
    "goals": "goals:progress_ready",
}


def _claim_value(name: str, summary: dict[str, Any]) -> Any:
    if name == "runtime":
        return bool(summary.get("runtime_ready", False)) and not bool(summary.get("runtime_missing", False))
    if name == "continuity":
        return bool(summary.get("same_system", False)) and not bool(summary.get("has_contradiction", False))
    if name == "pressure":
        return bool(summary.get("pressure_ready", False))
    if name == "recovery":
        return bool(summary.get("compatible_snapshot_ready", False))
    if name == "codebase":
        return bool(summary.get("scope_ready", False)) and bool(summary.get("verification_ready", False))
    if name in {"evolution", "source_evolution"}:
        return bool(summary.get("beneficial", False))
    if name == "goals":
        return bool(summary.get("current_goal_title", "")) and not bool(summary.get("current_goal_requires_user", False))
    return None


def claims_from_world_model(
    model: dict[str, Any],
    *,
    authority_evidence: dict[str, list[dict[str, Any]]] | None = None,
) -> dict[str, dict[str, Any]]:
    """Convert world-model summaries into claims without trusting the summaries.

    Domain booleans remain proposed claims until independent evidence certifies the
    exact requested scope. Freshness, confidence, or a pressure score do not grant
    authority by themselves.
    """
    evidence_map = dict(authority_evidence or {})
    domains = dict(model.get("domains") or {})
    claims: dict[str, dict[str, Any]] = {}

    for name, scope in _DOMAIN_SCOPES.items():
        domain = dict(domains.get(name) or {})
        summary = dict(domain.get("summary") or {})
        claim = make_claim(
            claim_id=f"world_model:{name}",
            claim_type=f"world_model.{name}",
            value=_claim_value(name, summary),
            source=f"world_model:{name}",
            requested_scope=[scope],
            provenance=[str(domain.get("source", name))],
            assumptions=["world_model_summary_is_not_reality"],
            contradictions=["domain_marked_blocking"] if bool(domain.get("blocking", False)) else [],
            observed_at_utc=str(domain.get("observed_at_utc", model.get("time_utc", "")) or ""),
            revocation_conditions=[
                "new_contradictory_observation",
                "source_becomes_stale",
                "verifier_independence_failure",
            ],
        )
        certified: Claim = certify_claim(claim, evidence_map.get(name, []))
        claims[name] = certified.to_dict()

    return claims


def claim_permits(claims: dict[str, dict[str, Any]], domain: str, scope: str) -> bool:
    claim = dict(claims.get(str(domain), {}) or {})
    return bool(
        claim.get("status") == "provisional"
        and float(claim.get("authority", 0.0) or 0.0) > 0.0
        and str(scope) in set(str(item) for item in claim.get("demonstrated_scope", []))
        and not list(claim.get("contradictions", []))
    )
