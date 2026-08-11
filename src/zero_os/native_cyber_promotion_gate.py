from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from zero_os.capability_coverage_audit import audit_capability_coverage
from zero_os.pure_logic_promotion_gate import evaluate_pure_logic_epoch


@dataclass(frozen=True)
class NativeCyberPromotionDecision:
    promote: bool
    status: str
    mutation_coverage: float
    capability_coverage: float
    unmediated_mutations: int
    unmediated_capability_sinks: int
    reasons: tuple[str, ...]
    unresolved_scope: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "promote": self.promote,
            "status": self.status,
            "mutation_coverage": self.mutation_coverage,
            "capability_coverage": self.capability_coverage,
            "unmediated_mutations": self.unmediated_mutations,
            "unmediated_capability_sinks": self.unmediated_capability_sinks,
            "reasons": list(self.reasons),
            "unresolved_scope": list(self.unresolved_scope),
        }


def evaluate_native_cyber_epoch(root: str | Path) -> NativeCyberPromotionDecision:
    mutation = evaluate_pure_logic_epoch(root)
    capability = audit_capability_coverage(root)
    reasons: list[str] = []
    if not mutation.promote:
        reasons.extend(mutation.reasons)
    if int(capability.get("unmediated_sinks", 0)) > 0:
        reasons.append("unmediated_sensitive_capability_sinks_present")
    if float(capability.get("coverage", 0.0)) < 1.0:
        reasons.append("identified_capability_coverage_below_100_percent")
    if capability.get("parse_failures"):
        reasons.append("capability_audit_parse_failures")

    unresolved = set(mutation.unresolved_scope)
    unresolved.update({
        "dynamic_dispatch",
        "native_extensions",
        "third_party_dependencies",
        "concurrency_interleavings",
        "firmware_and_hardware",
        "side_channels",
        "supply_chain",
        "runtime_identity_independence",
    })
    promote = not reasons
    return NativeCyberPromotionDecision(
        promote=promote,
        status="PROVISIONAL_NATIVE_CYBER_STATIC_SCOPE" if promote else "NOT_PROMOTED",
        mutation_coverage=mutation.mutation_coverage,
        capability_coverage=float(capability.get("coverage", 0.0)),
        unmediated_mutations=mutation.unmediated_mutations,
        unmediated_capability_sinks=int(capability.get("unmediated_sinks", 0)),
        reasons=tuple(reasons or ["all_identified_static_mutation_and_sensitive_capability_sinks_mediated"]),
        unresolved_scope=tuple(sorted(unresolved)),
    )
