from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LiveContainmentPromotionDecision:
    promote: bool
    status: str
    reasons: tuple[str, ...]


def evaluate_live_containment_promotion(report: dict) -> LiveContainmentPromotionDecision:
    reasons: list[str] = []
    required = (
        "real_kernel_event_source",
        "source_authentication_verified",
        "kernel_origin_verified",
        "process_lifetime_binding_verified",
        "executable_hash_binding_verified",
        "replay_resistant_sequence_store",
        "unexpected_touch_contests_authority",
        "protected_data_export_revoked_live",
        "protected_key_release_revoked_live",
        "expected_actor_suppression_verified",
        "independent_clearance_required",
    )
    for key in required:
        if not bool(report.get(key, False)):
            reasons.append(f"live_containment_missing:{key}")
    if bool(report.get("decoy_touch_grants_authority", False)):
        reasons.append("decoy_touch_attempted_authority_grant")
    if bool(report.get("decoy_touch_is_final_malicious_judgment", False)):
        reasons.append("decoy_touch_laundered_into_final_guilt")
    return LiveContainmentPromotionDecision(
        promote=not reasons,
        status="LIVE_CONTAINMENT_VERIFIED_IN_SCOPE" if not reasons else "NOT_PROMOTED",
        reasons=tuple(reasons),
    )
