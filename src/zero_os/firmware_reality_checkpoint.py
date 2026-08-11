from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
from typing import Iterable


@dataclass(frozen=True)
class FirmwareCheckpoint:
    device_identity: str
    boot_measurement_root: str
    authority_trace_head: str
    reality_ledger_head: str
    control_plane_digest: str
    monotonic_counter: int
    witness_id: str
    witness_signature: str = ""


def checkpoint_digest(checkpoint: FirmwareCheckpoint) -> str:
    payload = "|".join((
        checkpoint.device_identity,
        checkpoint.boot_measurement_root,
        checkpoint.authority_trace_head,
        checkpoint.reality_ledger_head,
        checkpoint.control_plane_digest,
        str(checkpoint.monotonic_counter),
        checkpoint.witness_id,
    ))
    return sha256(payload.encode("utf-8")).hexdigest()


def verify_checkpoint_progression(previous: FirmwareCheckpoint | None, current: FirmwareCheckpoint) -> dict:
    reasons: list[str] = []
    if not current.device_identity:
        reasons.append("device_identity_missing")
    if not current.boot_measurement_root:
        reasons.append("boot_measurement_root_missing")
    if not current.authority_trace_head:
        reasons.append("authority_trace_head_missing")
    if not current.reality_ledger_head:
        reasons.append("reality_ledger_head_missing")
    if not current.control_plane_digest:
        reasons.append("control_plane_digest_missing")
    if not current.witness_id:
        reasons.append("external_witness_identity_missing")
    if previous is not None:
        if previous.device_identity != current.device_identity:
            reasons.append("device_identity_changed")
        if current.monotonic_counter <= previous.monotonic_counter:
            reasons.append("monotonic_counter_not_advanced")
    return {
        "ok": not reasons,
        "reasons": reasons,
        "checkpoint_digest": checkpoint_digest(current),
        "externally_signed": bool(current.witness_signature),
        "self_certification_permitted": False,
    }
