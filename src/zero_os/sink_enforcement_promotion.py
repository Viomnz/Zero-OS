from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SinkEnforcementEvidence:
    protected_read_rechecks_live_containment: bool
    broker_key_release_rechecks_live_containment: bool
    protected_export_rechecks_live_containment: bool
    export_actuator_rechecks_live_containment: bool
    containment_revision_enforced: bool
    missing_process_state_fails_closed: bool
    independent_clearance_does_not_restore_sensitive_authority: bool
    path_logic_final_authority: bool
    process_identity_kernel_bound: bool = False
    real_kernel_or_broker_enforcement_demonstrated: bool = False
    evidence_provenance: tuple[str, ...] = ()


@dataclass(frozen=True)
class SinkEnforcementPromotionDecision:
    promote: bool
    status: str
    reasons: tuple[str, ...]
    demonstrated_scope: str


def evaluate_sink_enforcement_promotion(evidence: SinkEnforcementEvidence) -> SinkEnforcementPromotionDecision:
    reasons: list[str] = []
    checks = {
        "protected_read_sink_not_live_bound": evidence.protected_read_rechecks_live_containment,
        "broker_key_release_not_live_bound": evidence.broker_key_release_rechecks_live_containment,
        "protected_export_not_live_bound": evidence.protected_export_rechecks_live_containment,
        "export_actuator_not_live_bound": evidence.export_actuator_rechecks_live_containment,
        "containment_revision_not_enforced": evidence.containment_revision_enforced,
        "missing_process_state_not_fail_closed": evidence.missing_process_state_fails_closed,
        "process_identity_not_kernel_bound": evidence.process_identity_kernel_bound,
        "clearance_restores_sensitive_authority_without_reearning": evidence.independent_clearance_does_not_restore_sensitive_authority,
        "real_runtime_enforcement_not_demonstrated": evidence.real_kernel_or_broker_enforcement_demonstrated,
    }
    for reason, survived in checks.items():
        if not survived:
            reasons.append(reason)
    if evidence.path_logic_final_authority:
        reasons.append("path_logic_became_final_authority")
    if not evidence.evidence_provenance:
        reasons.append("sink_enforcement_provenance_missing")

    return SinkEnforcementPromotionDecision(
        promote=not reasons,
        status="LIVE_SINK_CONTAINMENT_VERIFIED_IN_SCOPE" if not reasons else "BLOCK_SINK_ENFORCEMENT_PROMOTION",
        reasons=tuple(reasons),
        demonstrated_scope=(
            "kernel-bound process identity plus sink contract and external runtime enforcement evidence"
            if not reasons
            else "software sink contract only; production containment not demonstrated"
        ),
    )


def sink_promotion_invariants() -> dict:
    return {
        "caller_boolean_cannot_replace_external_enforcement_evidence": True,
        "caller_process_label_cannot_replace_kernel_identity": True,
        "path_logic_final_authority": False,
        "promotion_requires_all_sensitive_sinks": True,
        "software_contract_is_not_kernel_reality": True,
    }
