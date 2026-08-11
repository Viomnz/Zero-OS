from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class CompatibilityState(str, Enum):
    CANONICAL = "CANONICAL"
    COMPATIBLE_IMPLEMENTATION = "COMPATIBLE_IMPLEMENTATION"
    LEGACY_EVIDENCE_ONLY = "LEGACY_EVIDENCE_ONLY"
    CONTESTED = "CONTESTED"


@dataclass(frozen=True)
class ArchitectureCompatibility:
    component: str
    state: CompatibilityState
    reasons: tuple[str, ...]
    may_define_pure_logic: bool = False
    may_grant_final_authority: bool = False


LEGACY_ARCHITECTURE_RULES: dict[str, tuple[str, ...]] = {
    "conscious_machine_architecture": (
        "functional_self_modeling_does_not_prove_phenomenal_consciousness",
        "identity_continuity_cannot_become_immutable_identity_authority",
        "majority_or_reliability_consensus_cannot_become_reality_authority",
        "self_improvement_requires_independent_scope_pressure_and_rollback",
    ),
    "perfect_zero": (
        "perfection_is_not_a_supported_terminal_state",
        "contradiction_is_not_automatically_impurity",
    ),
    "omni_zero": (
        "integration_is_a_method_not_final_authority",
        "coexistence_requires_scope_and_relation_evidence",
    ),
    "singular_zero": (
        "single_privileged_architecture_is_not_canonical",
        "plural_architecture_competition_must_remain_possible",
    ),
    "legacy_cure_recursion_beacon": (
        "recursion_pass_is_pressure_evidence_only",
        "survival_certificate_requires_scope_provenance_expiry_and_revocation",
    ),
}


def classify_architecture(component: str) -> ArchitectureCompatibility:
    name = str(component or "").strip().lower()
    if name in {"pure_logic", "zero_ai_current_foundation"}:
        return ArchitectureCompatibility(
            component=name,
            state=CompatibilityState.CANONICAL,
            reasons=("current_provisional_foundation",),
        )
    if name in LEGACY_ARCHITECTURE_RULES:
        return ArchitectureCompatibility(
            component=name,
            state=CompatibilityState.LEGACY_EVIDENCE_ONLY,
            reasons=LEGACY_ARCHITECTURE_RULES[name],
        )
    return ArchitectureCompatibility(
        component=name,
        state=CompatibilityState.CONTESTED,
        reasons=("compatibility_not_yet_demonstrated",),
    )


def legacy_may_override_foundation(component: str) -> bool:
    result = classify_architecture(component)
    return bool(result.may_define_pure_logic or result.may_grant_final_authority)
