from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

from zero_os.native_cyber_promotion_gate import evaluate_native_cyber_epoch
from zero_os.whole_repo_capability_audit import audit_whole_repository


@dataclass(frozen=True)
class EnforcementPromotionDecision:
    promote: bool
    status: str
    reasons: tuple[str, ...]
    whole_repo_coverage: float
    whole_repo_unmediated: int
    native_cyber_status: str
    unresolved_scope: tuple[str, ...]

    def to_dict(self) -> dict:
        return asdict(self)


def evaluate_enforcement_epoch(root: str | Path) -> EnforcementPromotionDecision:
    whole = audit_whole_repository(root)
    native = evaluate_native_cyber_epoch(root)
    reasons: list[str] = []

    if int(whole.get("unmediated_sinks", 0)) != 0:
        reasons.append("whole_repository_sensitive_sink_bypass_present")
    if float(whole.get("mediation_coverage", 0.0)) < 1.0:
        reasons.append("whole_repository_identified_capability_coverage_below_100_percent")
    if not bool(getattr(native, "promote", False)):
        reasons.append("native_cyber_epoch_not_promoted")

    unresolved = set(whole.get("limitations", []))
    unresolved.update(getattr(native, "unresolved_scope", ()) or ())
    unresolved.update(
        {
            "process_execution_migration_incomplete_until_all_direct_subprocess_calls_are_replaced_or_guarded",
            "entrypoint_to_sink_runtime_trace_coverage_not_independently_certified",
        }
    )

    promote = not reasons
    return EnforcementPromotionDecision(
        promote=promote,
        status="PROVISIONAL_ENFORCED_STATIC_SCOPE" if promote else "NOT_PROMOTED",
        reasons=tuple(reasons or ["all_identified_static_sensitive_sinks_mediated"]),
        whole_repo_coverage=float(whole.get("mediation_coverage", 0.0)),
        whole_repo_unmediated=int(whole.get("unmediated_sinks", 0)),
        native_cyber_status=str(getattr(native, "status", "UNKNOWN")),
        unresolved_scope=tuple(sorted(unresolved)),
    )
