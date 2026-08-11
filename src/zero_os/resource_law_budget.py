from __future__ import annotations

from dataclasses import dataclass


_LEVELS = {"low": 1, "medium": 2, "high": 3, "critical": 4}


@dataclass(frozen=True)
class VerificationBudget:
    depth: int
    required_evidence_groups: int
    require_independent_outcome: bool
    require_formal_invariant_check: bool
    require_reversible_path: bool


def allocate_verification_budget(
    *,
    consequence: str,
    urgency: str = "medium",
    reversibility: str = "high",
    information_gain: str = "medium",
) -> VerificationBudget:
    consequence_level = _LEVELS.get(str(consequence).lower(), 2)
    urgency_level = _LEVELS.get(str(urgency).lower(), 2)
    reversibility_level = _LEVELS.get(str(reversibility).lower(), 2)
    info_level = _LEVELS.get(str(information_gain).lower(), 2)

    irreversibility = 5 - reversibility_level
    depth = max(1, min(5, consequence_level + max(0, irreversibility - 1)))
    evidence_groups = 1 if depth <= 2 else 2 if depth <= 4 else 3

    # Urgency may change which investigation path is chosen, but it cannot erase
    # critical verification requirements. It can only reduce optional depth by one.
    if urgency_level >= 4 and consequence_level < 4:
        depth = max(1, depth - 1)

    return VerificationBudget(
        depth=depth,
        required_evidence_groups=evidence_groups,
        require_independent_outcome=consequence_level >= 3,
        require_formal_invariant_check=consequence_level >= 4 or irreversibility >= 4,
        require_reversible_path=consequence_level >= 3,
    )
