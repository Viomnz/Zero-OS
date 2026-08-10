from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable

from zero_os.execution_authority_ticket import consume_execution_ticket
from zero_os.mutation_registry import canonical_mutation_kind, mutation_class


@dataclass(frozen=True)
class KernelDecision:
    allowed: bool
    action_kind: str
    reason: str
    required_scope: str = ""
    risk: str = ""
    authority: dict | None = None


def authorize_runtime_mutation(cwd: str, action_kind: str) -> KernelDecision:
    """Single fail-closed runtime boundary for all registered mutations.

    The kernel does not accept confidence, readiness, planner score, LLM output,
    memory weight, or self-reported verifier counts as authority inputs.
    A mutating action must consume a fresh single-use Pure Logic ticket created
    by final_action_authority after exact claim/evidence checks survive.
    """
    canonical = canonical_mutation_kind(action_kind)
    spec = mutation_class(canonical)
    if spec is None:
        return KernelDecision(False, canonical, "unknown_mutation_kind")
    ticket = consume_execution_ticket(cwd, canonical)
    if not bool(ticket.get("ok", False)):
        return KernelDecision(
            False,
            canonical,
            "fresh_scoped_authority_missing",
            required_scope=spec.required_scope,
            risk=spec.risk,
            authority=ticket,
        )
    ticket_scope = str((ticket.get("ticket") or {}).get("required_scope", ""))
    if ticket_scope != spec.required_scope:
        return KernelDecision(
            False,
            canonical,
            "ticket_scope_mismatch",
            required_scope=spec.required_scope,
            risk=spec.risk,
            authority=ticket,
        )
    return KernelDecision(
        True,
        canonical,
        "provisional_scoped_authority",
        required_scope=spec.required_scope,
        risk=spec.risk,
        authority=ticket,
    )


def runtime_kernel_status() -> dict:
    from zero_os.mutation_registry import MUTATION_CLASSES

    return {
        "kernel": "pure_logic_runtime_kernel",
        "registered_mutation_classes": len(MUTATION_CLASSES),
        "confidence_grants_authority": False,
        "memory_grants_authority": False,
        "llm_grants_authority": False,
        "unknown_mutation_default": "deny",
        "ticket_semantics": "fresh_single_use_exact_scope",
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
    }
