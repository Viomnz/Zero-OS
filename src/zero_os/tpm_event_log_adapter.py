from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Iterable

from zero_os.hardware_attestation import PcrValue


@dataclass(frozen=True)
class EventLogRecord:
    sequence: int
    pcr_index: int
    event_type: str
    digest_sha256: str
    payload_sha256: str


@dataclass(frozen=True)
class EventLogDecision:
    verified: bool
    status: str
    reasons: tuple[str, ...]
    event_log_root_sha256: str
    reconstructed_pcrs: tuple[PcrValue, ...]
    authority_granted: bool = False


def _is_sha256(value: str) -> bool:
    text = str(value).lower()
    return len(text) == 64 and all(ch in "0123456789abcdef" for ch in text)


def _extend(old_hex: str, event_digest_hex: str) -> str:
    return hashlib.sha256(bytes.fromhex(old_hex) + bytes.fromhex(event_digest_hex)).hexdigest()


def reconstruct_event_log(records: Iterable[EventLogRecord]) -> EventLogDecision:
    rows = tuple(sorted(records, key=lambda row: int(row.sequence)))
    reasons: list[str] = []
    if not rows:
        reasons.append("event_log_empty")
    expected_sequence = None
    pcrs: dict[int, str] = {}
    canonical: list[dict] = []
    for row in rows:
        if expected_sequence is None:
            expected_sequence = int(row.sequence)
        if int(row.sequence) != expected_sequence:
            reasons.append("event_log_sequence_gap_or_reorder")
            expected_sequence = int(row.sequence)
        expected_sequence += 1
        if int(row.pcr_index) < 0:
            reasons.append(f"event_log_pcr_invalid:{row.pcr_index}")
            continue
        if not _is_sha256(row.digest_sha256):
            reasons.append(f"event_digest_invalid:{row.sequence}")
            continue
        if not _is_sha256(row.payload_sha256):
            reasons.append(f"event_payload_digest_invalid:{row.sequence}")
            continue
        current = pcrs.get(int(row.pcr_index), "00" * 32)
        pcrs[int(row.pcr_index)] = _extend(current, str(row.digest_sha256).lower())
        canonical.append({
            "sequence": int(row.sequence),
            "pcr_index": int(row.pcr_index),
            "event_type": str(row.event_type),
            "digest_sha256": str(row.digest_sha256).lower(),
            "payload_sha256": str(row.payload_sha256).lower(),
        })
    root = hashlib.sha256(json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    reconstructed = tuple(PcrValue(index=index, digest_sha256=digest) for index, digest in sorted(pcrs.items()))
    return EventLogDecision(
        verified=not reasons,
        status="EVENT_LOG_RECONSTRUCTED" if not reasons else "EVENT_LOG_CONTESTED",
        reasons=tuple(reasons),
        event_log_root_sha256=root,
        reconstructed_pcrs=reconstructed,
        authority_granted=False,
    )


def compare_reconstructed_pcrs(reconstructed: Iterable[PcrValue], quoted: Iterable[PcrValue]) -> tuple[str, ...]:
    left = {int(row.index): str(row.digest_sha256).lower() for row in reconstructed}
    right = {int(row.index): str(row.digest_sha256).lower() for row in quoted}
    reasons: list[str] = []
    for index in sorted(set(left) | set(right)):
        if index not in left:
            reasons.append(f"event_log_missing_quoted_pcr:{index}")
        elif index not in right:
            reasons.append(f"quote_missing_reconstructed_pcr:{index}")
        elif left[index] != right[index]:
            reasons.append(f"event_log_pcr_mismatch:{index}")
    return tuple(reasons)
