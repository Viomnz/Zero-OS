from __future__ import annotations

from dataclasses import dataclass

from zero_os.os_isolation import OSIsolationDecision
from zero_os.protected_data_kernel_mediation import KernelMediationDecision
from zero_os.protected_key_release import KeyReleaseBrokerDescriptor
from zero_os.tpm_sealed_key_policy import TPMUnsealDecision


@dataclass(frozen=True)
class ProtectedDataPromotionDecision:
    promote: bool
    status: str
    reasons: tuple[str, ...]
    demonstrated_scope: tuple[str, ...]
    unresolved_scope: tuple[str, ...]


def evaluate_protected_data_promotion(
    *,
    capability_registry_report: dict,
    runtime_sink_report: dict,
    kernel_mediation_decision: KernelMediationDecision | None,
    key_broker_descriptor: KeyReleaseBrokerDescriptor | None,
    breach_pressure_report: dict | None,
    os_isolation_decision: OSIsolationDecision | None = None,
    tpm_unseal_decision: TPMUnsealDecision | None = None,
) -> ProtectedDataPromotionDecision:
    """Fail closed on claims that important files remain protected after compromise.

    API mediation cannot certify same-privilege containment. The stronger v24
    promotion target requires structured kernel mediation, an OS-isolated broker,
    and TPM-sealed key eligibility bound to measured machine state. None of these
    evidence layers grants execution authority by itself.
    """
    reasons: list[str] = []
    capability = dict(capability_registry_report or {})
    runtime = dict(runtime_sink_report or {})
    pressure = dict(breach_pressure_report or {})

    if not bool(capability.get("read_export_separated", False)):
        reasons.append("protected_data_read_export_capabilities_not_separated")
    if not bool(capability.get("destination_bound_export", False)):
        reasons.append("protected_data_export_not_destination_bound")
    if not bool(runtime.get("exact_revision_grant_required", False)):
        reasons.append("protected_data_runtime_not_revision_bound")
    if not bool(runtime.get("compromise_shrinks_authority", False)):
        reasons.append("compromise_does_not_shrink_sensitive_authority")
    if not bool(runtime.get("ciphertext_at_rest_required", False)):
        reasons.append("protected_data_not_ciphertext_at_rest")
    if bool(runtime.get("runtime_holds_master_keys", True)):
        reasons.append("ordinary_runtime_holds_protected_data_master_keys")

    if kernel_mediation_decision is None:
        reasons.append("kernel_or_hardware_data_mediation_not_verified")
    else:
        if not kernel_mediation_decision.containment_demonstrated:
            reasons.append("kernel_mediation_not_demonstrated")
            reasons.extend(kernel_mediation_decision.reasons)
        if kernel_mediation_decision.authority_granted:
            reasons.append("kernel_mediation_attempted_authority_laundering")

    if key_broker_descriptor is None:
        reasons.append("protected_key_broker_not_configured")
    else:
        if not key_broker_descriptor.production_ready():
            reasons.append("protected_key_broker_not_production_isolated")
        if key_broker_descriptor.runtime_can_read_master_keys:
            reasons.append("protected_key_broker_exposes_master_keys_to_runtime")

    if os_isolation_decision is None:
        reasons.append("os_isolation_not_verified")
    else:
        if not os_isolation_decision.isolated:
            reasons.append("os_isolation_not_demonstrated")
            reasons.extend(os_isolation_decision.reasons)
        if os_isolation_decision.authority_granted:
            reasons.append("os_isolation_attempted_authority_laundering")

    if tpm_unseal_decision is None:
        reasons.append("tpm_sealed_key_policy_not_verified")
    else:
        if not tpm_unseal_decision.unseal_eligible:
            reasons.append("tpm_sealed_key_policy_not_demonstrated")
            reasons.extend(tpm_unseal_decision.reasons)
        if tpm_unseal_decision.key_released:
            reasons.append("promotion_evidence_must_not_release_real_key")
        if tpm_unseal_decision.authority_granted:
            reasons.append("tpm_unseal_attempted_authority_laundering")

    required_pressure = (
        "compromised_process_cannot_read_without_grant",
        "read_grant_cannot_export",
        "wrong_destination_blocked",
        "stale_revision_blocked",
        "compromise_revokes_sensitive_path",
        "direct_ciphertext_read_does_not_reveal_plaintext",
        "runtime_cannot_read_master_key",
        "same_privilege_direct_file_bypass_blocked",
        "runtime_cannot_ptrace_broker",
        "runtime_cannot_mount_protected_store",
        "wrong_measured_boot_state_cannot_unseal",
    )
    if not pressure:
        reasons.append("breach_pressure_not_run")
    else:
        for key in required_pressure:
            if not bool(pressure.get(key, False)):
                reasons.append(f"breach_pressure_failed:{key}")

    demonstrated = [
        "software_capability_separation",
        "exact_data_revision_binding",
        "destination_bound_export_contract",
        "compromise_driven_authority_shrink_request",
        "ciphertext_at_rest_contract",
        "external_key_broker_contract",
    ]
    if os_isolation_decision is not None and os_isolation_decision.isolated:
        demonstrated.append("os_identity_and_process_isolation")
    if tpm_unseal_decision is not None and tpm_unseal_decision.unseal_eligible:
        demonstrated.append("measured_state_bound_key_unseal_contract")

    unresolved: list[str] = []
    if kernel_mediation_decision is None or not kernel_mediation_decision.containment_demonstrated:
        unresolved.extend(("same_privilege_direct_filesystem_bypass", "kernel_filesystem_mediation", "network_clipboard_ipc_usb_sink_mediation"))
    if key_broker_descriptor is None or not key_broker_descriptor.production_ready():
        unresolved.append("separate_os_identity_key_broker")
    if os_isolation_decision is None or not os_isolation_decision.isolated:
        unresolved.extend(("broker_uid_isolation", "ptrace_and_namespace_isolation"))
    if tpm_unseal_decision is None or not tpm_unseal_decision.unseal_eligible:
        unresolved.append("hardware_backed_key_release")

    return ProtectedDataPromotionDecision(
        promote=not reasons,
        status="PROTECTED_DATA_HARDWARE_CONTAINMENT_VERIFIED_IN_SCOPE" if not reasons else "NOT_PROMOTED",
        reasons=tuple(reasons),
        demonstrated_scope=tuple(demonstrated),
        unresolved_scope=tuple(dict.fromkeys(unresolved)),
    )
