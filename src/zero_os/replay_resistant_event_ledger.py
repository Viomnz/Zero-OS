from __future__ import annotations

from dataclasses import dataclass, field
import hashlib


@dataclass(frozen=True)
class EventSequenceRecord:
    source: str
    source_event_id: str
    sequence: int
    event_digest: str


@dataclass
class ReplayResistantEventLedger:
    last_sequence_by_source: dict[str, int] = field(default_factory=dict)
    seen_event_ids: set[str] = field(default_factory=set)
    chain_head: str = "GENESIS"

    def accept(self, record: EventSequenceRecord) -> tuple[bool, str]:
        event_key = f"{record.source}:{record.source_event_id}"
        if event_key in self.seen_event_ids:
            return False, "event_replay_detected"
        last = int(self.last_sequence_by_source.get(record.source, 0))
        if record.sequence <= last:
            return False, "non_monotonic_event_sequence"
        if not record.event_digest:
            return False, "event_digest_missing"
        material = f"{self.chain_head}|{record.source}|{record.source_event_id}|{record.sequence}|{record.event_digest}"
        self.chain_head = hashlib.sha256(material.encode("utf-8")).hexdigest()
        self.last_sequence_by_source[record.source] = record.sequence
        self.seen_event_ids.add(event_key)
        return True, "event_sequence_accepted"


def event_digest(*parts: object) -> str:
    material = "|".join(str(p) for p in parts)
    return hashlib.sha256(material.encode("utf-8")).hexdigest()
