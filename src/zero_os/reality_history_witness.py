from __future__ import annotations

import base64
import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

from zero_os.authority_runtime_trace import verify_trace_chain
from zero_os.security_control_plane import load_state, verify_history_chain

try:
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives import serialization
    _CRYPTO_AVAILABLE = True
except Exception:
    InvalidSignature = Exception
    serialization = None
    _CRYPTO_AVAILABLE = False


def _canonical(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


@dataclass(frozen=True)
class RealityHistoryCheckpoint:
    authority_trace_head: str
    authority_trace_events: int
    security_control_digest: str
    security_control_revision: int
    witness_id: str
    witness_time_utc: str
    signature: str

    def unsigned_payload(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("signature", None)
        return data


def current_history_subject(cwd: str) -> dict[str, Any]:
    trace = verify_trace_chain(cwd)
    control = verify_history_chain(cwd)
    state = load_state(cwd)
    return {
        "authority_trace_head": str(trace.get("head_digest", "")),
        "authority_trace_events": int(trace.get("event_count", 0) or 0),
        "security_control_digest": state.digest(),
        "security_control_revision": int(state.revision),
        "local_trace_ok": bool(trace.get("ok", False)),
        "local_control_history_ok": bool(control.get("ok", False)),
    }


def verify_external_checkpoint(cwd: str, checkpoint: RealityHistoryCheckpoint, witness_public_key_pem: bytes) -> dict[str, Any]:
    """Verify a checkpoint signed outside Zero-OS's ordinary runtime domain.

    This module intentionally has no witness-signing function and stores no
    witness private key. A locally self-produced hash chain is not independent
    evidence of its own history.
    """
    if not _CRYPTO_AVAILABLE:
        return {"ok": False, "reason": "asymmetric_crypto_unavailable"}
    subject = current_history_subject(cwd)
    if not subject["local_trace_ok"] or not subject["local_control_history_ok"]:
        return {"ok": False, "reason": "local_history_invalid_before_external_witness"}
    exact = (
        checkpoint.authority_trace_head == subject["authority_trace_head"]
        and checkpoint.authority_trace_events == subject["authority_trace_events"]
        and checkpoint.security_control_digest == subject["security_control_digest"]
        and checkpoint.security_control_revision == subject["security_control_revision"]
    )
    if not exact:
        return {"ok": False, "reason": "external_checkpoint_subject_mismatch"}
    try:
        public_key = serialization.load_pem_public_key(witness_public_key_pem)
        signature = base64.b64decode(checkpoint.signature, validate=True)
        public_key.verify(signature, _canonical(checkpoint.unsigned_payload()))
    except (ValueError, InvalidSignature, TypeError):
        return {"ok": False, "reason": "external_witness_signature_invalid"}
    return {
        "ok": True,
        "reason": "external_history_witness_verified",
        "witness_id": checkpoint.witness_id,
        "authority_trace_head": checkpoint.authority_trace_head,
        "security_control_revision": checkpoint.security_control_revision,
        "scope": "history_subject_at_checkpoint_only",
    }
