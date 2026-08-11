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
    _state_path(cwd).write_text(json.dumps(asdict(state), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    record = {"time_utc": _utc_now(), "state_digest": state.digest(), **event}
    with _history_path(cwd).open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")


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


def _apply_mutation(
    cwd: str,
    mutation: str,
    payload: dict[str, Any],
    *,
    antivirus_policy: dict[str, Any],
    suppressions: list[dict[str, Any]],
    firewall_policy: dict[str, Any],
    recovery_policy: dict[str, Any],
    feed_generation: int,
    authority_generation: int,
) -> tuple[int, int]:
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
        suppressions[:] = [x for x in suppressions if str(x.get("id", "")) != suppression_id]
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
        _new_key(cwd, "antivirus_feed", feed_generation)
    elif mutation == "rotate_authority_key":
        authority_generation += 1
        _new_key(cwd, "authority", authority_generation)
    else:
        raise ValueError(f"unknown_security_control_mutation:{mutation}")
    return feed_generation, authority_generation


def mutate_batch(cwd: str, operations: Iterable[dict[str, Any]]) -> dict:
    handoff = _authorized_security_change(cwd)
    if not handoff.get("ok"):
        return {"ok": False, "reason": "security_control_plane_authority_missing", "handoff": handoff}
    current = load_state(cwd)
    antivirus_policy = dict(current.antivirus_policy)
    suppressions = list(current.suppressions)
    firewall_policy = dict(current.firewall_policy)
    recovery_policy = dict(current.recovery_policy)
    feed_generation = current.feed_key_generation
    authority_generation = current.authority_key_generation
    normalized = [dict(item or {}) for item in operations]
    try:
        for operation in normalized:
            feed_generation, authority_generation = _apply_mutation(
                cwd,
                str(operation.get("mutation", "")),
                dict(operation.get("payload") or {}),
                antivirus_policy=antivirus_policy,
                suppressions=suppressions,
                firewall_policy=firewall_policy,
                recovery_policy=recovery_policy,
                feed_generation=feed_generation,
                authority_generation=authority_generation,
            )
    except (ValueError, RuntimeError) as exc:
        return {"ok": False, "reason": str(exc)}

    updated = SecurityControlState(
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
    digest = hashlib.sha256(json.dumps(normalized, sort_keys=True, default=str).encode()).hexdigest()
    _persist(cwd, updated, {"mutation": "batch", "operation_count": len(normalized), "payload_digest": digest})
    return {"ok": True, "revision": updated.revision, "digest": updated.digest(), "state": asdict(updated), "operation_count": len(normalized)}


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
    if state.revision <= 1:
        return {"ok": True, "reason": "initial_revision", "revision": state.revision}
    lines = _history_path(cwd).read_text(encoding="utf-8", errors="replace").splitlines() if _history_path(cwd).exists() else []
    if len(lines) < state.revision - 1:
        return {"ok": False, "reason": "security_control_history_incomplete", "revision": state.revision}
    return {"ok": True, "reason": "security_control_history_present", "revision": state.revision, "history_records": len(lines)}
