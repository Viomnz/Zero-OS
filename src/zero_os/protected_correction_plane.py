from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable


@dataclass(frozen=True)
class CorrectionCandidate:
    candidate_id: str
    target: str
    proposer_id: str
    provenance: tuple[str, ...]
    invariant_checks: tuple[str, ...] = field(default_factory=tuple)
    pressure_results: tuple[str, ...] = field(default_factory=tuple)
    independent_evaluators: tuple[str, ...] = field(default_factory=tuple)
    rollback_reference: str = ""
    canary_reference: str = ""
    compatibility_reference: str = ""


@dataclass(frozen=True)
class CorrectionDecision:
    allowed: bool
    status: str
    reasons: tuple[str, ...]


def evaluate_correction_candidate(candidate: CorrectionCandidate) -> CorrectionDecision:
    reasons: list[str] = []
    if not candidate.provenance:
        reasons.append("provenance_missing")
    if not candidate.invariant_checks:
        reasons.append("formal_or_executable_invariant_checks_missing")
    if not candidate.pressure_results:
        reasons.append("adversarial_pressure_missing")
    evaluators = {str(x) for x in candidate.independent_evaluators if str(x)}
    if not evaluators:
        reasons.append("independent_evaluation_missing")
    if candidate.proposer_id in evaluators:
        reasons.append("proposer_cannot_be_sole_or_self_evaluator")
    if not candidate.rollback_reference:
        reasons.append("rollback_missing")
    if not candidate.canary_reference:
        reasons.append("canary_missing")
    if not candidate.compatibility_reference:
        reasons.append("compatibility_analysis_missing")
    return CorrectionDecision(not reasons, "ELIGIBLE_FOR_ISOLATED_CANARY" if not reasons else "BLOCKED", tuple(reasons))


@dataclass
class ProtectedCorrectionPlane:
    """Separates runtime tamper resistance from architecture revisability."""

    protected_targets: frozenset[str]
    runtime_writers: frozenset[str] = field(default_factory=frozenset)

    def runtime_write_allowed(self, actor_id: str, target: str) -> bool:
        if str(target) not in self.protected_targets:
            return True
        return str(actor_id) in self.runtime_writers

    def architecture_revision_allowed(self, candidate: CorrectionCandidate) -> CorrectionDecision:
        if candidate.target not in self.protected_targets:
            return CorrectionDecision(False, "BLOCKED", ("target_not_in_correction_plane",))
        return evaluate_correction_candidate(candidate)


def default_correction_plane() -> ProtectedCorrectionPlane:
    return ProtectedCorrectionPlane(
        protected_targets=frozenset(
            {
                "core_policy",
                "authority_kernel",
                "authority_ledger",
                "authority_root",
                "authority_runtime_trace",
                "capability_kernel",
                "correction_plane",
                "release_promotion_policy",
                "security_control_plane",
                "antivirus_policy",
                "antivirus_suppressions",
                "antivirus_feed_signing_keys",
                "cure_firewall_policy",
                "recovery_policy",
                "security_key_rotation",
                "protected_data_manifest",
                "protected_data_export_policy",
                "protected_data_key_release_policy",
                "protected_data_mediation_policy",
                "protected_data_broker_identity",
                "protected_data_broker_public_key",
                "protected_data_kernel_policy",
                "protected_data_cipher_policy",
                "zero_os_source",
                "firmware_policy",
                "firmware_boot_manifest",
                "firmware_root_public_keys",
                "firmware_rollback_counter",
                "firmware_recovery_policy",
                "firmware_reality_checkpoint",
                "firmware_update_authority",
            }
        ),
        runtime_writers=frozenset(),
    )
