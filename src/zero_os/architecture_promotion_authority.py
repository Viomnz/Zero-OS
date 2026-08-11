from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from zero_os.protected_correction_plane import CorrectionCandidate, ProtectedCorrectionPlane


@dataclass(frozen=True)
class ArchitecturePromotionDecision:
    promote: bool
    status: str
    reasons: tuple[str, ...]
    demonstrated_scope: tuple[str, ...]
    unresolved_scope: tuple[str, ...]


def evaluate_architecture_promotion(
    *,
    candidate: CorrectionCandidate,
    correction_plane: ProtectedCorrectionPlane,
    critical_invariants_passed: bool,
    independent_outcome_verified: bool,
    identified_authority_bypasses: int,
    identified_capability_bypasses: int,
    demonstrated_scope: Iterable[str],
    unresolved_scope: Iterable[str],
    runtime_integration_report: dict | None = None,
) -> ArchitecturePromotionDecision:
    """Promotion authority for the architecture itself.

    A constitutional design is not promoted merely because its modules exist.
    The identified runtime paths must also demonstrate that they actually depend
    on the authority kernel. One known bypass remains a veto.
    """
    reasons: list[str] = []
    correction = correction_plane.architecture_revision_allowed(candidate)
    if not correction.allowed:
        reasons.extend(correction.reasons)
    if not critical_invariants_passed:
        reasons.append("critical_invariants_not_proven_within_model")
    if not independent_outcome_verified:
        reasons.append("independent_outcome_not_verified")
    if int(identified_authority_bypasses) > 0:
        reasons.append("identified_authority_bypass_present")
    if int(identified_capability_bypasses) > 0:
        reasons.append("identified_capability_bypass_present")

    integration = dict(runtime_integration_report or {})
    if not integration:
        reasons.append("runtime_authority_integration_not_audited")
    elif not bool(integration.get("promotion_permitted", False)):
        reasons.append("runtime_authority_integration_incomplete")
        for item in list(integration.get("requirements", [])):
            if not bool(dict(item or {}).get("satisfied", False)):
                requirement_id = str(dict(item or {}).get("requirement_id", "unknown"))
                reasons.append(f"runtime_integration_missing:{requirement_id}")

    demonstrated = tuple(sorted({str(x) for x in demonstrated_scope if str(x)}))
    unresolved = tuple(sorted({str(x) for x in unresolved_scope if str(x)}))
    if not unresolved:
        unresolved = ("unknown_external_scope_remains",)

    return ArchitecturePromotionDecision(
        promote=not reasons,
        status="PROVISIONAL_PROMOTION_IN_DEMONSTRATED_SCOPE" if not reasons else "NOT_PROMOTED",
        reasons=tuple(reasons),
        demonstrated_scope=demonstrated,
        unresolved_scope=unresolved,
    )
