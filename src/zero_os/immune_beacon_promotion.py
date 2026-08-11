from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ImmuneBeaconPromotionDecision:
    promote: bool
    status: str
    reasons: tuple[str, ...]
    demonstrated_scope: tuple[str, ...]
    unresolved_scope: tuple[str, ...]


def evaluate_immune_beacon_promotion(
    *,
    gate_invariant_report: dict,
    pressure_report: dict | None,
    cryptographic_issuer_isolated: bool,
    independent_scope_certifier_present: bool,
    contradiction_memory_wired: bool,
    authority_kernel_consumes_beacon_as_nonfinal_evidence: bool,
) -> ImmuneBeaconPromotionDecision:
    reasons: list[str] = []
    gate = dict(gate_invariant_report or {})
    pressure = dict(pressure_report or {})

    required_false = (
        "beacon_is_final_authority",
        "beacon_may_mint_capability",
        "beacon_may_expand_scope",
        "beacon_may_self_renew",
    )
    for key in required_false:
        if bool(gate.get(key, True)):
            reasons.append(f"immune_beacon_authority_laundering:{key}")

    required_true = (
        "artifact_change_invalidates_old_beacon",
        "state_revision_change_invalidates_old_beacon",
        "contradiction_contests_beacon",
        "parent_revocation_contests_beacon",
        "issuer_independence_required",
        "scope_certifier_independence_required",
    )
    for key in required_true:
        if not bool(gate.get(key, False)):
            reasons.append(f"immune_beacon_invariant_missing:{key}")

    required_pressure = (
        "hash_change_blocked",
        "revision_change_blocked",
        "scope_expansion_blocked",
        "dependent_evidence_not_counted_independent",
        "expired_beacon_blocked",
        "contradiction_downgrades",
        "parent_revocation_propagates",
        "self_certification_blocked",
        "legacy_cure_beacon_not_authority",
    )
    if not pressure:
        reasons.append("immune_beacon_pressure_not_run")
    else:
        for key in required_pressure:
            if not bool(pressure.get(key, False)):
                reasons.append(f"immune_beacon_pressure_failed:{key}")

    if not cryptographic_issuer_isolated:
        reasons.append("immune_beacon_issuer_not_cryptographically_isolated")
    if not independent_scope_certifier_present:
        reasons.append("immune_beacon_scope_certifier_not_independent")
    if not contradiction_memory_wired:
        reasons.append("immune_beacon_contradiction_memory_not_wired")
    if not authority_kernel_consumes_beacon_as_nonfinal_evidence:
        reasons.append("authority_kernel_not_wired_to_nonfinal_beacon_evidence")

    unresolved: list[str] = []
    if not cryptographic_issuer_isolated:
        unresolved.append("external_or_hardware_backed_beacon_issuer")
    if not independent_scope_certifier_present:
        unresolved.append("independent_scope_certifier_runtime")
    if not contradiction_memory_wired:
        unresolved.append("contradiction_memory_runtime_propagation")
    if not authority_kernel_consumes_beacon_as_nonfinal_evidence:
        unresolved.append("authority_kernel_beacon_consumption_path")

    return ImmuneBeaconPromotionDecision(
        promote=not reasons,
        status="IMMUNE_BEACON_VERIFIED_IN_SCOPE" if not reasons else "NOT_PROMOTED",
        reasons=tuple(reasons),
        demonstrated_scope=(
            "revocable_survival_certificate_model",
            "artifact_and_revision_binding",
            "scope_limited_survival_evidence",
            "independence_aware_pressure_evidence",
            "legacy_cure_beacon_demoted_to_evidence",
        ),
        unresolved_scope=tuple(unresolved),
    )
