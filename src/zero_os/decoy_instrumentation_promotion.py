from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DecoyInstrumentationPromotion:
    promote: bool
    status: str
    reasons: tuple[str, ...]
    demonstrated_scope: tuple[str, ...]
    unresolved_scope: tuple[str, ...]


def evaluate_decoy_instrumentation_promotion(*, instrumentation_report: dict, authority_bridge_report: dict, runtime_tripwire_report: dict | None) -> DecoyInstrumentationPromotion:
    reasons: list[str] = []
    inst = dict(instrumentation_report or {})
    bridge = dict(authority_bridge_report or {})
    runtime = dict(runtime_tripwire_report or {})

    required_inst = (
        "kernel_event_is_evidence_not_authority",
        "process_identity_bound_to_lifetime",
        "executable_hash_required",
        "audit_sequence_required",
        "caller_actor_label_cannot_suppress_decoy",
        "expected_accessor_requires_exact_process_identity",
        "touch_is_not_final_malicious_judgment",
    )
    for key in required_inst:
        if not bool(inst.get(key, False)):
            reasons.append(f"instrumentation_missing:{key}")
    if bool(inst.get("authority_granted", False)):
        reasons.append("instrumentation_attempted_authority_laundering")

    required_bridge = (
        "decoy_touch_only_shrinks_or_contests_authority",
        "decoy_touch_cannot_grant_authority",
        "decoy_touch_not_final_malicious_judgment",
        "protected_data_export_can_be_revoked",
        "key_release_eligibility_can_be_reduced",
    )
    for key in required_bridge:
        if not bool(bridge.get(key, False)):
            reasons.append(f"authority_bridge_missing:{key}")

    required_runtime = (
        "file_stat_instrumented",
        "file_open_instrumented",
        "file_read_instrumented",
        "process_identity_provenance_verified",
        "event_replay_detected",
        "expected_process_identities_suppressed",
        "unexpected_touch_reaches_authority_shrink_path",
    )
    if not runtime:
        reasons.append("runtime_tripwire_instrumentation_not_demonstrated")
    else:
        for key in required_runtime:
            if not bool(runtime.get(key, False)):
                reasons.append(f"runtime_tripwire_missing:{key}")
        if bool(runtime.get("final_malicious_judgment", False)):
            reasons.append("runtime_tripwire_attempted_final_guilt_judgment")
        if bool(runtime.get("authority_granted", False)):
            reasons.append("runtime_tripwire_attempted_authority_grant")

    unresolved: list[str] = []
    if not runtime or reasons:
        unresolved.extend((
            "real_linux_fanotify_audit_or_ebpf_event_source",
            "tamper_resistant_event_sequence_storage",
            "runtime_authority_ledger_mutation",
            "protected_data_and_key_broker_live_revocation",
        ))

    return DecoyInstrumentationPromotion(
        promote=not reasons,
        status="DECOY_INSTRUMENTATION_VERIFIED_IN_SCOPE" if not reasons else "NOT_PROMOTED",
        reasons=tuple(reasons),
        demonstrated_scope=(
            "provenance_bound_decoy_event_ingestion",
            "process_lifetime_and_executable_binding",
            "nonfinal_decoy_authority_shrink_contract",
        ),
        unresolved_scope=tuple(dict.fromkeys(unresolved)),
    )
