from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _trace_path(cwd: str) -> Path:
    path = Path(cwd).resolve() / ".zero_os" / "authority" / "runtime_trace.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _digest(payload: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class AuthorityTraceEvent:
    trace_id: str
    event_kind: str
    principal_id: str
    authority_id: str
    objective_id: str
    action_kind: str
    subject_id: str
    state_revision: str
    artifact_id: str
    event_time_utc: str
    payload_digest: str
    previous_event_digest: str
    event_digest: str


def _last_digest(cwd: str) -> str:
    path = _trace_path(cwd)
    if not path.exists():
        return ""
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    if not lines:
        return ""
    try:
        return str(json.loads(lines[-1]).get("event_digest", ""))
    except Exception:
        return ""


def record_event(
    cwd: str,
    *,
    trace_id: str,
    event_kind: str,
    principal_id: str,
    authority_id: str,
    objective_id: str,
    action_kind: str,
    subject_id: str,
    state_revision: str,
    artifact_id: str,
    payload: dict[str, Any] | None = None,
) -> AuthorityTraceEvent:
    previous = _last_digest(cwd)
    core = {
        "trace_id": str(trace_id),
        "event_kind": str(event_kind),
        "principal_id": str(principal_id),
        "authority_id": str(authority_id),
        "objective_id": str(objective_id),
        "action_kind": str(action_kind),
        "subject_id": str(subject_id),
        "state_revision": str(state_revision),
        "artifact_id": str(artifact_id),
        "event_time_utc": _utc_now(),
        "payload_digest": _digest(payload or {}),
        "previous_event_digest": previous,
    }
    event_digest = _digest(core)
    event = AuthorityTraceEvent(**core, event_digest=event_digest)
    with _trace_path(cwd).open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(asdict(event), sort_keys=True) + "\n")
    return event


def read_trace(cwd: str, trace_id: str) -> list[dict[str, Any]]:
    path = _trace_path(cwd)
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            row = json.loads(line)
        except Exception:
            continue
        if str(row.get("trace_id", "")) == str(trace_id):
            out.append(row)
    return out


def verify_trace_chain(cwd: str) -> dict[str, Any]:
    path = _trace_path(cwd)
    if not path.exists():
        return {"ok": True, "event_count": 0, "reason": "trace_empty"}
    previous = ""
    count = 0
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            row = json.loads(line)
        except Exception:
            return {"ok": False, "reason": "trace_json_invalid", "event_count": count}
        recorded = str(row.get("event_digest", ""))
        unsigned = dict(row)
        unsigned.pop("event_digest", None)
        if str(unsigned.get("previous_event_digest", "")) != previous:
            return {"ok": False, "reason": "trace_chain_previous_digest_mismatch", "event_count": count}
        if _digest(unsigned) != recorded:
            return {"ok": False, "reason": "trace_event_digest_invalid", "event_count": count}
        previous = recorded
        count += 1
    return {"ok": True, "reason": "trace_chain_verified", "event_count": count, "head_digest": previous}


def certify_authority_trace(cwd: str, trace_id: str, *, required_events: Iterable[str] = ("constitutional_decision", "issuer_attestation", "runtime_consume", "sink_acknowledge", "outcome_verify")) -> dict[str, Any]:
    rows = read_trace(cwd, trace_id)
    kinds = [str(row.get("event_kind", "")) for row in rows]
    missing = [event for event in required_events if event not in kinds]
    bindings = {
        (str(row.get("principal_id", "")), str(row.get("authority_id", "")), str(row.get("objective_id", "")), str(row.get("action_kind", "")), str(row.get("subject_id", "")), str(row.get("state_revision", "")))
        for row in rows
    }
    return {
        "ok": bool(rows) and not missing and len(bindings) == 1,
        "trace_id": str(trace_id),
        "event_count": len(rows),
        "events": kinds,
        "missing_events": missing,
        "binding_consistent": len(bindings) == 1,
        "status": "CAUSAL_TRACE_SURVIVED_IN_RECORDED_SCOPE" if rows and not missing and len(bindings) == 1 else "CONTESTED",
    }
