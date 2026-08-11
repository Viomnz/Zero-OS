from __future__ import annotations

import hashlib
import json
import os
import secrets
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from zero_os.execution_authority_ticket import acknowledge_consumed_execution_ticket


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _root(cwd: str) -> Path:
    root = Path(cwd).resolve() / ".zero_os" / "security_control_plane"
    root.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(root, 0o700)
    except OSError:
        pass
    return root


def _state_path(cwd: str) -> Path:
    return _root(cwd) / "state.json"


def _history_path(cwd: str) -> Path:
    return _root(cwd) / "history.jsonl"


def _keys_dir(cwd: str) -> Path:
    path = _root(cwd) / "keys"
    path.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(path, 0o700)
    except OSError:
        pass
    return path


@dataclass(frozen=True)
class SecurityControlState:
    revision: int
    antivirus_policy: dict[str, Any] = field(default_factory=dict)
    suppressions: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    firewall_policy: dict[str, Any] = field(default_factory=dict)
    recovery_policy: dict[str, Any] = field(default_factory=dict)
    feed_key_generation: int = 1
    authority_key_generation: int = 1
    updated_at_utc: str = ""
    previous_digest: str = ""

    def digest(self) -> str:
        return hashlib.sha256(json.dumps(asdict(self), sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def default_state() -> SecurityControlState:
    return SecurityControlState(
        revision=1,
        antivirus_policy={
            "heuristic_threshold": 65,
            "auto_quarantine": False,
            "exclude_paths": [".git", ".zero_os/production/snapshots"],
            "response_mode": "manual",
        },
        suppressions=(),
        firewall_policy={"minimum_pressure": 80, "require_beacon_verification": True},
        recovery_policy={"rollback_required": True, "independent_outcome_required": True},
        updated_at_utc=_utc_now(),
    )


def load_state(cwd: str) -> SecurityControlState:
    path = _state_path(cwd)
    if not path.exists():
        state = default_state()
        path.write_text(json.dumps(asdict(state), indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return state
    raw = json.loads(path.read_text(encoding="utf-8", errors="replace") or "{}")
    return SecurityControlState(
        revision=int(raw.get("revision", 0) or 0),
        antivirus_policy=dict(raw.get("antivirus_policy") or {}),
        suppressions=tuple(dict(x) for x in raw.get("suppressions", []) if isinstance(x, dict)),
        firewall_policy=dict(raw.get("firewall_policy") or {}),
        recovery_policy=dict(raw.get("recovery_policy") or {}),
        feed_key_generation=int(raw.get("feed_key_generation", 1) or 1),
        authority_key_generation=int(raw.get("authority_key_generation", 1) or 1),
        updated_at_utc=str(raw.get("updated_at_utc", "")),
        previous_digest=str(raw.get("previous_digest", "")),
    )


def _persist(cwd: str, state: SecurityControlState, event: dict[str, Any]) -> None:
    record = {
        "time_utc": _utc_now(),
        "revision": state.revision,
        "previous_digest": state.previous_digest,
        "state_digest": state.digest(),
        **event,
    }
    # History first, state second. If the state write fails, history contains an
    # unapplied candidate revision and verification will contest it rather than
    # silently accepting a state transition with no record.
    with _history_path(cwd).open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")
        handle.flush()
        try:
            os.fsync(handle.fileno())
        except OSError:
            pass
    _state_path(cwd).write_text(json.dumps(asdict(state), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _authorized_security_change(cwd: str) -> dict:
    return acknowledge_consumed_execution_ticket(cwd, "policy_change")


def _new_key(cwd: str, purpose: str, generation: int) -> Path:
    path = _keys_dir(cwd) / f"{purpose}.g{int(generation)}.key"
    if path.exists():
        raise RuntimeError("security control key generation already exists")
    path.write_bytes(secrets.token_bytes(32))
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return path


def _plan_mutations(current: SecurityControlState, operations: list[dict[str, Any]]) -> tuple[SecurityControlState, list[tuple[str, int]]]:
    antivirus_policy = dict(current.antivirus_policy)
    suppressions = list(current.suppressions)
    firewall_policy = dict(current.firewall_policy)
    recovery_policy = dict(current.recovery_policy)
    feed_generation = current.feed_key_generation
    authority_generation = current.authority_key_generation
    key_creations: list[tuple[str, int]] = []

    for operation in operations:
        mutation = str(operation.get("mutation", ""))
        payload = dict(operation.get("payload") or {})
        if mutation == "set_antivirus_policy":
            key = str(payload.get("key", ""))
            if not key:
                raise ValueError("security_policy_key_missing")
            antivirus_policy[key] = payload.get("value")
        elif mutation == "add_suppression":
            item = dict(payload.get("item") or {})
            if not item.get("signature_id"):
                raise ValueError("suppression_signature_missing")
            suppressions.append(item)
        elif mutation == "remove_suppression":
            suppression_id = str(payload.get("id", ""))
            if not suppression_id:
                raise ValueError("suppression_id_missing")
            suppressions = [x for x in suppressions if str(x.get("id", "")) != suppression_id]
        elif mutation == "set_firewall_policy":
            key = str(payload.get("key", ""))
            if not key:
                raise ValueError("firewall_policy_key_missing")
            firewall_policy[key] = payload.get("value")
        elif mutation == "set_recovery_policy":
            key = str(payload.get("key", ""))
            if not key:
                raise ValueError("recovery_policy_key_missing")
            recovery_policy[key] = payload.get("value")
        elif mutation == "rotate_feed_key":
            feed_generation += 1
            key_creations.append(("antivirus_feed", feed_generation))
        elif mutation == "rotate_authority_key":
            authority_generation += 1
            key_creations.append(("authority", authority_generation))
        else:
            raise ValueError(f"unknown_security_control_mutation:{mutation}")

    planned = SecurityControlState(
        revision=current.revision + 1,
        antivirus_policy=antivirus_policy,
        suppressions=tuple(suppressions),
        firewall_policy=firewall_policy,
        recovery_policy=recovery_policy,
        feed_key_generation=feed_generation,
        authority_key_generation=authority_generation,
        updated_at_utc=_utc_now(),
        previous_digest=current.digest(),
    )
    return planned, key_creations


def mutate_batch(cwd: str, operations: Iterable[dict[str, Any]]) -> dict:
    normalized = [dict(item or {}) for item in operations]
    if not normalized:
        return {"ok": False, "reason": "security_control_operations_missing"}
    current = load_state(cwd)
    try:
        planned, key_creations = _plan_mutations(current, normalized)
    except ValueError as exc:
        return {"ok": False, "reason": str(exc)}

    # Validate first, consume authority second. Malformed requests cannot burn an
    # otherwise valid single-use authority handoff.
    handoff = _authorized_security_change(cwd)
    if not handoff.get("ok"):
        return {"ok": False, "reason": "security_control_plane_authority_missing", "handoff": handoff}

    created: list[Path] = []
    try:
        for purpose, generation in key_creations:
            created.append(_new_key(cwd, purpose, generation))
        payload_digest = hashlib.sha256(json.dumps(normalized, sort_keys=True, default=str).encode()).hexdigest()
        _persist(cwd, planned, {
            "mutation": "batch",
            "operation_count": len(normalized),
            "payload_digest": payload_digest,
            "authority_trace_id": str((handoff.get("ticket") or {}).get("ticket_id", "")),
        })
    except Exception as exc:
        for path in created:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass
        return {"ok": False, "reason": f"security_control_commit_failed:{type(exc).__name__}"}

    return {
        "ok": True,
        "revision": planned.revision,
        "digest": planned.digest(),
        "state": asdict(planned),
        "operation_count": len(normalized),
        "trace_id": str((handoff.get("ticket") or {}).get("ticket_id", "")),
    }


def mutate_state(cwd: str, mutation: str, payload: dict[str, Any]) -> dict:
    return mutate_batch(cwd, ({"mutation": mutation, "payload": payload},))


def control_key(cwd: str, purpose: str, generation: int | None = None) -> bytes:
    state = load_state(cwd)
    if generation is None:
        generation = state.feed_key_generation if purpose == "antivirus_feed" else state.authority_key_generation
    path = _keys_dir(cwd) / f"{purpose}.g{int(generation)}.key"
    if not path.exists():
        _new_key(cwd, purpose, int(generation))
    data = path.read_bytes()
    if len(data) != 32:
        raise RuntimeError("security control key invalid")
    return data


def verify_history_chain(cwd: str) -> dict:
    state = load_state(cwd)
    path = _history_path(cwd)
    if state.revision <= 1:
        return {"ok": True, "reason": "initial_revision", "revision": state.revision, "history_records": 0}
    if not path.exists():
        return {"ok": False, "reason": "security_control_history_missing", "revision": state.revision}

    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            row = json.loads(line)
        except Exception:
            return {"ok": False, "reason": "security_control_history_json_invalid", "revision": state.revision}
        if isinstance(row, dict):
            rows.append(row)
    if len(rows) < state.revision - 1:
        return {"ok": False, "reason": "security_control_history_incomplete", "revision": state.revision, "history_records": len(rows)}

    relevant = rows[-(state.revision - 1):]
    expected_revision = 2
    previous_digest = ""
    for index, row in enumerate(relevant):
        revision = int(row.get("revision", 0) or 0)
        if revision != expected_revision:
            return {"ok": False, "reason": "security_control_history_revision_gap", "expected_revision": expected_revision, "observed_revision": revision}
        row_previous = str(row.get("previous_digest", ""))
        if index > 0 and row_previous != previous_digest:
            return {"ok": False, "reason": "security_control_history_chain_mismatch", "revision": revision}
        previous_digest = str(row.get("state_digest", ""))
        if not previous_digest:
            return {"ok": False, "reason": "security_control_history_digest_missing", "revision": revision}
        expected_revision += 1

    if previous_digest != state.digest():
        return {"ok": False, "reason": "security_control_head_digest_mismatch", "revision": state.revision}
    if relevant[-1].get("previous_digest") != state.previous_digest:
        return {"ok": False, "reason": "security_control_previous_digest_mismatch", "revision": state.revision}
    return {
        "ok": True,
        "reason": "security_control_history_chain_verified",
        "revision": state.revision,
        "history_records": len(rows),
        "head_digest": state.digest(),
    }
