from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from zero_os.pure_logic_epoch_audit import audit_repository


@dataclass(frozen=True)
class PromotionDecision:
    promote: bool
    status: str
    reasons: tuple[str, ...]
    mutation_coverage: float
    unmediated_mutations: int
    unresolved_scope: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "promote": self.promote,
            "status": self.status,
            "reasons": list(self.reasons),
            "mutation_coverage": self.mutation_coverage,
            "unmediated_mutations": self.unmediated_mutations,
            "unresolved_scope": list(self.unresolved_scope),
        }


def evaluate_pure_logic_epoch(root: str | Path) -> PromotionDecision:
    audit = audit_repository(root)
    reasons: list[str] = []
    unresolved = list(audit.get("limitations", []))

    if int(audit.get("unmediated_candidates", 0)) > 0:
        reasons.append("unmediated_mutation_candidates_present")
    if float(audit.get("mediation_coverage", 0.0)) < 1.0:
        reasons.append("identified_mutation_coverage_below_100_percent")

    # Pure Logic deliberately distinguishes identified-code coverage from total
    # behavioral scope. Even perfect static coverage is not global certification.
    if not unresolved:
        unresolved.append("runtime_behavioral_scope_not_independently_certified")

    promote = not reasons
    return PromotionDecision(
        promote=promote,
        status="PROVISIONAL_STATIC_SCOPE" if promote else "NOT_PROMOTED",
        reasons=tuple(reasons or ["all_identified_static_mutation_candidates_mediated"]),
        mutation_coverage=float(audit.get("mediation_coverage", 0.0)),
        unmediated_mutations=int(audit.get("unmediated_candidates", 0)),
        unresolved_scope=tuple(unresolved),
    )
