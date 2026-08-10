from __future__ import annotations

from typing import Any

from zero_os.world_model_claims import claim_permits, claims_from_world_model


_CALL_REQUIREMENTS = {
    "repair_continuity": ("continuity", "continuity:same_system"),
    "ensure_background_agent": ("runtime", "runtime:ready"),
    "enable_runtime_loop": ("runtime", "runtime:ready"),
    "stabilize_recovery": ("recovery", "recovery:ready"),
    "run_code_canary": ("codebase", "codebase:mutation_ready"),
    "run_code_fix_loop": ("codebase", "codebase:mutation_ready"),
    "goal_progress": ("goals", "goals:progress_ready"),
    "self_derivation_revalidate": ("pressure", "pressure:survived"),
    "evolution_auto_run": ("evolution", "evolution:beneficial"),
    "source_evolution_auto_run": ("source_evolution", "source_evolution:beneficial"),
}

_READ_ONLY_OR_REFRESH = {"observe", "wait_for_user", "run_runtime", "jobs_tick"}


def enforce_governor_authority(
    governor: dict[str, Any],
    world_model: dict[str, Any],
    *,
    authority_evidence: dict[str, list[dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    """Separate governor recommendation from action authority.

    The existing governor may rank what it thinks should happen. This gate decides
    whether the recommendation has independently certified scope. A denied call is
    converted to observation rather than being allowed to mutate on confidence.
    """
    proposed = dict(governor or {})
    call = str(proposed.get("call", "observe") or "observe")
    claims = claims_from_world_model(dict(world_model or {}), authority_evidence=authority_evidence)

    if call in _READ_ONLY_OR_REFRESH:
        return {
            **proposed,
            "proposed_call": call,
            "authority_gate": "not_required",
            "authority_claims": claims,
            "confidence_is_non_authoritative": True,
        }

    requirement = _CALL_REQUIREMENTS.get(call)
    if requirement is None:
        return {
            **proposed,
            "proposed_call": call,
            "call": "observe",
            "mode": "contested",
            "authority_gate": "blocked",
            "authority_reason": "unknown_mutating_call_has_no_claim_mapping",
            "authority_claims": claims,
            "confidence_is_non_authoritative": True,
        }

    domain, scope = requirement
    if not claim_permits(claims, domain, scope):
        return {
            **proposed,
            "proposed_call": call,
            "call": "observe",
            "mode": "contested",
            "authority_gate": "blocked",
            "authority_reason": "independent_scope_authority_missing",
            "required_domain": domain,
            "required_scope": scope,
            "authority_claims": claims,
            "confidence_is_non_authoritative": True,
        }

    return {
        **proposed,
        "proposed_call": call,
        "authority_gate": "provisional",
        "required_domain": domain,
        "required_scope": scope,
        "authority_claims": claims,
        "confidence_is_non_authoritative": True,
    }
