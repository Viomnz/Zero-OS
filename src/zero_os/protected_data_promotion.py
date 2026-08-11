from __future__ import annotations

from dataclasses import dataclass


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
    kernel_mediation_report: dict | None,
    breach_pressure_report: dict | None,
) -> ProtectedDataPromotionDecision:
    """Fail closed on claims that important files remain protected after compromise.

    Python/API mediation is not equivalent to OS/kernel mediation. Production
    containment requires evidence that same-privilege code cannot bypass the
    protected sink and read/decrypt/export the data directly.
    """
    reasons: list[str] = []
    capability = dict(capability_registry_report or {})
    runtime = dict(runtime_sink_report or {})
    kernel = dict(kernel_mediation_report or {})
    pressure = dict(breach_pressure_report or {})

    if not bool(capability.get("read_export_separated", False)):
        reasons.append("protected_data_read_export_capabilities_not_separated")
    if not bool(capability.get("destination_bound_export", False)):
        reasons.append("protected_data_export_not_destination_bound")
    if not bool(runtime.get("exact_revision_grant_required", False)):
        reasons.append("protected_data_runtime_not_revision_bound")
    if not bool(runtime.get("compromise_shrinks_authority", False)):
        reasons.append("compromise_does_not_shrink_sensitive_authority")

    # External/kernel evidence cannot be substituted by a caller saying "secure".
    required_kernel = (
        "verified",
        "filesystem_mediation",
        "key_release_isolated",
        "export_sinks_mediated",
        "same_privilege_bypass_tested",
    )
    if not kernel:
        reasons.append("kernel_or_hardware_data_mediation_not_verified")
    else:
        for key in required_kernel:
            if not bool(kernel.get(key, False)):
                reasons.append(f"kernel_mediation_missing:{key}")
        if bool(kernel.get("authority_granted", False)):
            reasons.append("kernel_mediation_report_attempted_authority_laundering")

    required_pressure = (
        "compromised_process_cannot_read_without_grant",
        "read_grant_cannot_export",
        "wrong_destination_blocked",
        "stale_revision_blocked",
        "compromise_revokes_sensitive_path",
    )
    if not pressure:
        reasons.append("breach_pressure_not_run")
    else:
        for key in required_pressure:
            if not bool(pressure.get(key, False)):
                reasons.append(f"breach_pressure_failed:{key}")

    demonstrated = (
        "software_capability_separation",
        "exact_data_revision_binding",
        "destination_bound_export_contract",
        "compromise_driven_authority_shrink_request",
    )
    unresolved = []
    if not kernel or not all(bool(kernel.get(key, False)) for key in required_kernel):
        unresolved.extend((
            "same_privilege_direct_filesystem_bypass",
            "hardware_backed_key_release",
            "kernel_filesystem_mediation",
            "network_clipboard_ipc_usb_sink_mediation",
        ))

    return ProtectedDataPromotionDecision(
        promote=not reasons,
        status="PROTECTED_DATA_CONTAINMENT_VERIFIED_IN_SCOPE" if not reasons else "NOT_PROMOTED",
        reasons=tuple(reasons),
        demonstrated_scope=demonstrated,
        unresolved_scope=tuple(unresolved),
    )
