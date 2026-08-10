from __future__ import annotations

from typing import Any

from zero_os.pure_logic_authority import certify_candidate
from zero_os.zero_ai_llm import LLMBackend, backend_from_environment, propose


def reason(
    objective: str,
    *,
    observations: list[dict[str, Any]] | None = None,
    constraints: list[str] | None = None,
    requested_scope: list[str] | None = None,
    independent_evidence: list[dict[str, Any]] | None = None,
    backend: LLMBackend | None = None,
) -> dict[str, Any]:
    """Run the Zero AI discovery -> Pure Logic authority split.

    The LLM generates proposals. Independent evidence, not LLM confidence or
    fluency, determines whether any requested scope receives provisional
    authority. No mutation is performed here.
    """
    active_backend = backend or backend_from_environment()
    llm = propose(
        objective,
        observations=observations,
        constraints=constraints,
        requested_scope=requested_scope,
        backend=active_backend,
    )

    candidate = {
        "source": "zero_ai_llm",
        "scope": list(llm.get("requested_scope", [])),
    }
    authority = certify_candidate(candidate, list(independent_evidence or []))

    return {
        "ok": True,
        "objective": str(objective or ""),
        "proposal": llm,
        "authority": authority,
        "separation": {
            "discovery_source": "zero_ai_llm",
            "scope_certifier": "pure_logic_authority",
            "llm_confidence_can_grant_authority": False,
            "llm_requested_scope_is_demonstrated_scope": False,
            "mutation_performed": False,
        },
    }
