from __future__ import annotations

from dataclasses import dataclass

from zero_os.decoy_beacon import DecoyBeacon
from zero_os.decoy_beacon_response import DecoyResponse, respond_to_decoy_touch
from zero_os.decoy_event_ingest import DecoyKernelEvent, DecoyIngestDecision, ingest_decoy_event


@dataclass(frozen=True)
class DecoyAuthorityEffect:
    status: str
    evidence_accepted: bool
    contest_process_authority: bool
    revoke_sensitive_export: bool
    reduce_key_release_eligibility: bool
    require_investigation: bool
    quarantine_eligible: bool
    preserve_forensics: bool
    final_malicious_judgment: bool = False
    authority_granted: bool = False


def evaluate_decoy_authority_effect(beacon: DecoyBeacon, event: DecoyKernelEvent) -> tuple[DecoyIngestDecision, DecoyResponse | None, DecoyAuthorityEffect]:
    ingest = ingest_decoy_event(beacon, event)
    if not ingest.accepted or ingest.touch is None:
        return ingest, None, DecoyAuthorityEffect(
            status="DECOY_EVENT_NOT_ACTIONABLE",
            evidence_accepted=False,
            contest_process_authority=False,
            revoke_sensitive_export=False,
            reduce_key_release_eligibility=False,
            require_investigation=True,
            quarantine_eligible=False,
            preserve_forensics=True,
        )

    _, response = respond_to_decoy_touch(beacon, ingest.touch)
    suspicious = bool(response.contest_process_authority)
    effect = DecoyAuthorityEffect(
        status="DECOY_AUTHORITY_SHRINK_REQUEST" if suspicious else "DECOY_NO_AUTHORITY_CHANGE",
        evidence_accepted=True,
        contest_process_authority=suspicious,
        revoke_sensitive_export=bool(response.revoke_protected_data_export),
        reduce_key_release_eligibility=suspicious,
        require_investigation=bool(response.require_investigation),
        quarantine_eligible=bool(response.quarantine_eligible),
        preserve_forensics=bool(response.preserve_forensics),
        final_malicious_judgment=False,
        authority_granted=False,
    )
    return ingest, response, effect


def bridge_invariants() -> dict:
    return {
        "decoy_touch_only_shrinks_or_contests_authority": True,
        "decoy_touch_cannot_grant_authority": True,
        "decoy_touch_not_final_malicious_judgment": True,
        "protected_data_export_can_be_revoked": True,
        "key_release_eligibility_can_be_reduced": True,
    }
