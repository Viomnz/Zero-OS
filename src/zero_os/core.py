"""Immutable Zero-OS core policy."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from zero_os.types import Task


SurvivalState = Literal["ok", "blocked"]


@dataclass(frozen=True)
class CorePolicy:
    """Core behavior that cannot be changed at runtime."""

    immutable_core: bool
    authentication_required: bool
    policy_name: str
    unified_entity_name: str
    merged_components: tuple[str, ...]
    recursion_enforced: bool
    max_recursion_depth: int
    survival_protocols: tuple[str, ...]


CORE_POLICY = CorePolicy(
    immutable_core=True,
    authentication_required=False,
    policy_name="zero-os-immutable-no-auth",
    unified_entity_name="Zero OS Unified Core",
    merged_components=(
        "Zero OS base",
        "Zero AI Instances",
        "Compressed Data Units",
        "Zero OS Universe (OSU)",
    ),
    recursion_enforced=True,
    max_recursion_depth=24,
    survival_protocols=(
        "immutable-laws",
        "single-entity-unification",
        "recursion-law-enforcement",
        "survival-first-execution",
    ),
)


def run_survival_protocols(policy: CorePolicy, task: Task) -> tuple[SurvivalState, str]:
    if not policy.immutable_core:
        return ("blocked", "Core integrity violation: immutable_core must remain true.")
    if policy.recursion_enforced and task.recursion_depth > policy.max_recursion_depth:
        return (
            "blocked",
            (
                "Recursion law enforced: "
                f"depth={task.recursion_depth} exceeds limit={policy.max_recursion_depth}."
            ),
        )
    return ("ok", "survival protocols active")
