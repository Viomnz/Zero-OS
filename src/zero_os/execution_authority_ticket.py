from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from zero_os.authority_root_of_trust import AuthorityAttestation, verify_attestation


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _ticket_path(cwd: str) -> Path:
    path = Path(cwd).resolve() / ".zero_os" / "authority" / "execution_tickets.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text("[]\n", encoding="utf-8")
    return path


@dataclass(frozen=True)
class ExecutionAuthorityTicket:
    ticket_id: str
    action_kind: str
    authority_id: str
    objective_id: str
    principal_id: str
    subject_id: str
    required_scope: str
    state_revision: str
    issued_at_utc: str
    expires_at_utc: str
    attestation: AuthorityAttestation
    consumed: bool = False
    sink_acknowledged: bool = False


def _attestation_from_dict(raw: dict) -> AuthorityAttestation | None:
    try:
        return AuthorityAttestation(**dict(raw or {}))
    except (TypeError, ValueError):
        return None


def _load(cwd: str) -> list[dict]:
    try:
        payload = json.loads(_ticket_path(cwd).read_text(encoding="utf-8", errors="replace") or "[]")
    except (ValueError, OSError):
        return []
    return [dict(item) for item in payload if isinstance(item, dict)]


def _save(cwd: str, rows: list[dict]) -> None:
    _ticket_path(cwd).write_text(json.dumps(rows, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def issue_execution_ticket(*args, **kwargs):
    """Legacy arbitrary minting is forbidden in v8."""
    raise PermissionError("execution tickets may only be minted by the authority root issuer")


def ticket_from_attestation(cwd: str, attestation: AuthorityAttestation) -> ExecutionAuthorityTicket:
    verified = verify_attestation(cwd, attestation)
    if not verified.get("ok", False):
        raise PermissionError(str(verified.get("reason", "authority attestation invalid")))
    if attestation.artifact_kind != "execution_ticket":
        raise PermissionError("attestation is not an execution ticket")
    scopes = tuple(attestation.scopes)
    if len(scopes) != 1:
        raise PermissionError("execution ticket must bind exactly one required scope")
    ticket = ExecutionAuthorityTicket(
        ticket_id=attestation.artifact_id,
        action_kind=attestation.action_kind,
        authority_id=attestation.authority_id,
        objective_id=attestation.objective_id,
        principal_id=attestation.principal_id,
        subject_id=attestation.subject_id,
        required_scope=scopes[0],
        state_revision=attestation.state_revision,
        issued_at_utc=attestation.issued_at_utc,
        expires_at_utc=attestation.expires_at_utc,
        attestation=attestation,
    )
    rows = _load(cwd)
    rows.append(asdict(ticket))
    _save(cwd, rows[-200:])
    return ticket


def _parse_utc(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _row_attestation_valid(cwd: str, row: dict, action_kind: str) -> tuple[bool, str]:
    attestation = _attestation_from_dict(dict(row.get("attestation") or {}))
    if attestation is None:
        return False, "execution_ticket_attestation_missing"
    checked = verify_attestation(cwd, attestation)
    if not checked.get("ok", False):
        return False, str(checked.get("reason", "execution_ticket_attestation_invalid"))
    exact = (
        attestation.artifact_kind == "execution_ticket"
        and attestation.artifact_id == str(row.get("ticket_id", ""))
        and attestation.action_kind == str(action_kind)
        and attestation.action_kind == str(row.get("action_kind", ""))
        and attestation.authority_id == str(row.get("authority_id", ""))
        and attestation.objective_id == str(row.get("objective_id", ""))
        and attestation.principal_id == str(row.get("principal_id", ""))
        and attestation.subject_id == str(row.get("subject_id", ""))
        and attestation.state_revision == str(row.get("state_revision", ""))
        and tuple(attestation.scopes) == (str(row.get("required_scope", "")),)
    )
    return (True, "attested_execution_ticket_exact_match") if exact else (False, "execution_ticket_binding_mismatch")


def consume_execution_ticket(cwd: str, action_kind: str, *, now_utc: datetime | None = None) -> dict:
    now = now_utc or _utc_now()
    rows = _load(cwd)
    selected = -1
    reject_reason = "execution_authority_ticket_missing_or_expired"
    for index in range(len(rows) - 1, -1, -1):
        row = rows[index]
        if bool(row.get("consumed", False)) or str(row.get("action_kind", "")) != str(action_kind):
            continue
        expiry = _parse_utc(str(row.get("expires_at_utc", "")))
        if expiry is None or now > expiry:
            continue
        valid, reason = _row_attestation_valid(cwd, row, action_kind)
        if not valid:
            reject_reason = reason
            continue
        selected = index
        break
    if selected < 0:
        return {"ok": False, "reason": reject_reason}
    rows[selected]["consumed"] = True
    rows[selected]["consumed_at_utc"] = now.isoformat()
    rows[selected].setdefault("sink_acknowledged", False)
    ticket = dict(rows[selected])
    _save(cwd, rows)
    return {"ok": True, "ticket": ticket, "reason": "attested_execution_ticket_consumed"}


def acknowledge_consumed_execution_ticket(cwd: str, action_kind: str, *, now_utc: datetime | None = None, max_handoff_seconds: int = 10) -> dict:
    now = now_utc or _utc_now()
    max_age = max(1, min(int(max_handoff_seconds), 60))
    rows = _load(cwd)
    selected = -1
    reject_reason = "fresh_consumed_ticket_handoff_missing"
    for index in range(len(rows) - 1, -1, -1):
        row = rows[index]
        if str(row.get("action_kind", "")) != str(action_kind):
            continue
        if not bool(row.get("consumed", False)) or bool(row.get("sink_acknowledged", False)):
            continue
        valid, reason = _row_attestation_valid(cwd, row, action_kind)
        if not valid:
            reject_reason = reason
            continue
        consumed_at = _parse_utc(str(row.get("consumed_at_utc", "")))
        expiry = _parse_utc(str(row.get("expires_at_utc", "")))
        if consumed_at is None or expiry is None or now > expiry:
            continue
        age = (now - consumed_at).total_seconds()
        if age < 0 or age > max_age:
            continue
        selected = index
        break
    if selected < 0:
        return {"ok": False, "reason": reject_reason}
    rows[selected]["sink_acknowledged"] = True
    rows[selected]["sink_acknowledged_at_utc"] = now.isoformat()
    ticket = dict(rows[selected])
    _save(cwd, rows)
    return {"ok": True, "ticket": ticket, "reason": "attested_sink_handoff_acknowledged"}
