"""Zero-OS protected, revision-capable Pure Logic core policy."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from zero_os.types import Task


SurvivalState = Literal["ok", "blocked"]


@dataclass(frozen=True)
class CorePolicy:
    """Runtime constitution.

    Protection is operational, not epistemic: ordinary runtime components may not
    rewrite the governing core, but a stronger replacement may be promoted through
    the protected correction plane after independent verification and rollback.
    """

    runtime_core_protected: bool
    revision_capable: bool
    privileged_identity_authority_required: bool
    policy_name: str
    unified_entity_name: str
    merged_components: tuple[str, ...]
    recursion_enforced: bool
    max_recursion_depth: int
    master_laws: tuple[str, ...]
    constitutional_invariants: tuple[str, ...]

    @property
    def immutable_core(self) -> bool:
        """Legacy compatibility only. Epistemic immutability is intentionally false."""
        return False

    @property
    def authentication_required(self) -> bool:
        """Legacy compatibility only.

        Identity requirements are consequence- and capability-scoped rather than a
        universal login boolean. Privileged operations require strong identity evidence.
        """
        return self.privileged_identity_authority_required

    @property
    def survival_protocols(self) -> tuple[str, ...]:
        """Legacy status-display alias for current constitutional invariants.

        Older SystemCapability status output still asks for ``survival_protocols``.
        Keeping this read-only alias avoids a stale-attribute crash without restoring
        the superseded protocol set or granting it independent authority.
        """
        return self.constitutional_invariants


CORE_POLICY = CorePolicy(
    runtime_core_protected=True,
    revision_capable=True,
    privileged_identity_authority_required=True,
    policy_name="zero-os-protected-revisable-scoped-authority",
    unified_entity_name="Zero OS Pure Logic Authority Core",
    merged_components=(
        "Zero OS base",
        "Zero AI Instances",
        "Compressed Data Units",
        "Zero OS Universe (OSU)",
    ),
    recursion_enforced=True,
    max_recursion_depth=24,
    master_laws=(
        "Reality",
        "Survival",
        "Investigation",
        "Plurality",
        "Path",
        "Resource",
    ),
    constitutional_invariants=(
        "nothing_internal_is_reality",
        "authority_is_provisional_scoped_and_revocable",
        "contradictions_trigger_investigation",
        "viable_alternatives_survive_until_evidence_separates_them",
        "actions_minimize_unnecessary_irreversible_damage",
        "verification_resources_scale_with_consequence_and_information_gain",
        "runtime_core_is_protected_but_never_epistemically_immutable",
        "no_component_may_certify_its_own_authority",
    ),
)


def run_survival_protocols(policy: CorePolicy, task: Task) -> tuple[SurvivalState, str]:
    if not policy.runtime_core_protected:
        return ("blocked", "Core protection violation: runtime authority boundary disabled.")
    if not policy.revision_capable:
        return ("blocked", "Reality Law violation: governing architecture cannot be challenged or corrected.")
    if policy.recursion_enforced and task.recursion_depth > policy.max_recursion_depth:
        return (
            "blocked",
            (
                "Bounded recursion enforced: "
                f"depth={task.recursion_depth} exceeds limit={policy.max_recursion_depth}."
            ),
        )
    return ("ok", "protected revision-capable Pure Logic core active")
