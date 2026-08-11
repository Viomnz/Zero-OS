from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Iterable


@dataclass(frozen=True)
class RealityRecord:
    record_id: str
    subject_id: str
    claim_type: str
    value: Any
    provenance: tuple[str, ...] = field(default_factory=tuple)
    assumptions: tuple[str, ...] = field(default_factory=tuple)
    dependencies: tuple[str, ...] = field(default_factory=tuple)
    requested_scope: tuple[str, ...] = field(default_factory=tuple)
    demonstrated_scope: tuple[str, ...] = field(default_factory=tuple)
    contradictions: tuple[str, ...] = field(default_factory=tuple)
    status: str = "UNKNOWN"
    observed_at_utc: str = ""
    expires_at_utc: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


class RealityLedger:
    """Provenance-first ledger. Records are evidence-bearing claims, never reality itself."""

    def __init__(self) -> None:
        self.records: dict[str, RealityRecord] = {}

    def put(self, record: RealityRecord) -> None:
        self.records[record.record_id] = record

    def get(self, record_id: str) -> RealityRecord | None:
        return self.records.get(str(record_id))

    def contest(self, record_id: str, contradiction: str) -> RealityRecord:
        current = self.records[record_id]
        updated = RealityRecord(
            **{
                **current.to_dict(),
                "contradictions": current.contradictions + (str(contradiction),),
                "status": "CONTESTED",
            }
        )
        self.records[record_id] = updated
        return updated

    def active(self, record_id: str, *, now_utc: datetime | None = None) -> bool:
        record = self.get(record_id)
        if record is None or record.status in {"REVOKED", "SUPERSEDED", "HISTORICAL"}:
            return False
        if not record.expires_at_utc:
            return True
        now = now_utc or datetime.now(timezone.utc)
        try:
            expiry = datetime.fromisoformat(record.expires_at_utc.replace("Z", "+00:00"))
        except ValueError:
            return False
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)
        return now <= expiry.astimezone(timezone.utc)

    def unresolved_dependencies(self, record_id: str) -> tuple[str, ...]:
        record = self.records[record_id]
        return tuple(dep for dep in record.dependencies if dep not in self.records or not self.active(dep))


def make_reality_record(
    *,
    record_id: str,
    subject_id: str,
    claim_type: str,
    value: Any,
    provenance: Iterable[str],
    requested_scope: Iterable[str] = (),
    demonstrated_scope: Iterable[str] = (),
    assumptions: Iterable[str] = (),
    dependencies: Iterable[str] = (),
    status: str = "PROVISIONAL",
    expires_at_utc: str = "",
) -> RealityRecord:
    return RealityRecord(
        record_id=str(record_id),
        subject_id=str(subject_id),
        claim_type=str(claim_type),
        value=value,
        provenance=tuple(str(x) for x in provenance if str(x)),
        assumptions=tuple(str(x) for x in assumptions if str(x)),
        dependencies=tuple(str(x) for x in dependencies if str(x)),
        requested_scope=tuple(str(x) for x in requested_scope if str(x)),
        demonstrated_scope=tuple(str(x) for x in demonstrated_scope if str(x)),
        status=str(status),
        observed_at_utc=datetime.now(timezone.utc).isoformat(),
        expires_at_utc=str(expires_at_utc),
    )
