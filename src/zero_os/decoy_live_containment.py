from __future__ import annotations

from dataclasses import dataclass

from zero_os.decoy_beacon import DecoyBeacon
from zero_os.decoy_beacon_response import respond_to_decoy_touch
from zero_os.decoy_event_ingest import ingest_decoy_event
from zero_os.linux_decoy_event_adapter import LinuxAccessRecord, adapt_linux_access_record
from zero_os.live_containment_state import LiveContainmentRegistry
from zero_os.replay_resistant_event_ledger import EventSequenceRecord, ReplayResistantEventLedger, event_digest


@dataclass(frozen=True)
class LiveContainmentDecision:
    accepted: bool
    status: str
    reasons: tuple[str, ...]
    process_identity: str = ""
    authority_state: str = ""
    export_allowed: bool = True
    key_release_allowed: bool = True
    final_malicious_judgment: bool = False
    authority_granted: bool = False


def process_linux_decoy_event(
    *,
    beacon: DecoyBeacon,
    record: LinuxAccessRecord,
    event_ledger: ReplayResistantEventLedger,
    containment: LiveContainmentRegistry,
) -> LiveContainmentDecision:
    adapted = adapt_linux_access_record(record)
    if not adapted.accepted or adapted.event is None:
        return LiveContainmentDecision(False, adapted.status, adapted.reasons)

    event = adapted.event
    digest = event_digest(
        event.beacon_id,
        event.actor_id,
        event.process_id,
        event.process_start_time_ns,
        event.executable_hash,
        event.access_kind.value,
        event.object_path,
        event.observed_at,
    )
    accepted, seq_status = event_ledger.accept(EventSequenceRecord(
        source=event.source,
        source_event_id=event.source_event_id,
        sequence=event.kernel_audit_sequence,
        event_digest=digest,
    ))
    if not accepted:
        return LiveContainmentDecision(False, "DECOY_EVENT_REPLAY_OR_ORDER_REJECTED", (seq_status,))

    ingested = ingest_decoy_event(beacon, event)
    if not ingested.accepted or ingested.touch is None:
        return LiveContainmentDecision(False, ingested.status, ingested.reasons)

    verdict, response = respond_to_decoy_touch(beacon, ingested.touch)
    process_identity = ingested.touch.process_id
    if not verdict.suspicious:
        state = containment.get(process_identity)
        return LiveContainmentDecision(
            True,
            response.status,
            verdict.reasons,
            process_identity=process_identity,
            authority_state=state.authority_state,
            export_allowed=state.protected_data_export_allowed,
            key_release_allowed=state.protected_key_release_allowed,
        )

    state = containment.contest(process_identity, "unexpected_decoy_beacon_access")
    return LiveContainmentDecision(
        True,
        "LIVE_CONTAINMENT_APPLIED",
        verdict.reasons,
        process_identity=process_identity,
        authority_state=state.authority_state,
        export_allowed=state.protected_data_export_allowed,
        key_release_allowed=state.protected_key_release_allowed,
        final_malicious_judgment=False,
        authority_granted=False,
    )
