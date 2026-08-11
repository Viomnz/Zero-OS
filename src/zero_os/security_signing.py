from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime, timezone
from typing import Any

from zero_os.security_control_plane import control_key, load_state


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sign_antivirus_feed(cwd: str, feed: dict[str, Any]) -> dict[str, Any]:
    state = load_state(cwd)
    generation = state.feed_key_generation
    envelope = {
        "feed": feed,
        "signed_utc": _utc_now(),
        "key_generation": generation,
        "control_revision": state.revision,
        "control_digest": state.digest(),
    }
    envelope["signature"] = hmac.new(control_key(cwd, "antivirus_feed", generation), _canonical(envelope), hashlib.sha256).hexdigest()
    return envelope


def verify_antivirus_feed(cwd: str, envelope: dict[str, Any], *, minimum_version: int = 0) -> dict[str, Any]:
    if not isinstance(envelope, dict):
        return {"ok": False, "reason": "feed_envelope_invalid"}
    signature = str(envelope.get("signature", ""))
    unsigned = dict(envelope)
    unsigned.pop("signature", None)
    try:
        generation = int(unsigned.get("key_generation", 0))
    except (TypeError, ValueError):
        return {"ok": False, "reason": "feed_key_generation_invalid"}
    if generation <= 0:
        return {"ok": False, "reason": "feed_key_generation_invalid"}
    expected = hmac.new(control_key(cwd, "antivirus_feed", generation), _canonical(unsigned), hashlib.sha256).hexdigest()
    if not signature or not hmac.compare_digest(signature, expected):
        return {"ok": False, "reason": "feed_signature_invalid"}
    feed = unsigned.get("feed")
    if not isinstance(feed, dict) or not isinstance(feed.get("signatures", []), list):
        return {"ok": False, "reason": "feed_payload_invalid"}
    try:
        version = int(feed.get("version", 0))
    except (TypeError, ValueError):
        return {"ok": False, "reason": "feed_version_invalid"}
    if version < int(minimum_version):
        return {"ok": False, "reason": "feed_rollback_detected", "version": version, "minimum_version": int(minimum_version)}
    state = load_state(cwd)
    if generation > state.feed_key_generation:
        return {"ok": False, "reason": "feed_signed_by_unknown_future_generation"}
    return {
        "ok": True,
        "reason": "feed_signature_verified",
        "version": version,
        "key_generation": generation,
        "control_revision": unsigned.get("control_revision"),
    }
