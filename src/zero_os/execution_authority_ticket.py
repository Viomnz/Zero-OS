from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4


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
    subject_id: str
    required_scope: str
    state_revision: str
    issued_at_utc: str
    expires_at_utc: str
    consumed: bool = False


def _load(cwd: str) -> list[dict]:
    try:
        payload = json.loads(_ticket_path(cwd).read_text(encoding="utf-8", errors="replace") or "[]")
    except (ValueError, OSError):
        return []
    return [dict(item) for item in payload if isinstance(item, dict)]


def _save(cwd: str, rows: list[dict]) -> None:
    _ticket_path(cwd).write_text(json.dumps(rows, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def issue_execution_ticket(
    cwd: str,
    *,
    action_kind: str,
    authority_id: str,
    subject_id: str,
    required_scope: str,
    state_revision: str,
    ttl_seconds: int = 30,
) -> ExecutionAuthorityTicket:
    now = _utc_now()
    ticket = ExecutionAuthorityTicket(
        ticket_id=str(uuid4()),
        action_kind=str(action_kind),
        authority_id=str(authority_id),
        subject_id=str(subject_id),
        required_scope=str(required_scope),
        state_revision=str(state_revision),
        issued_at_utc=now.isoformat(),
        expires_at_utc=(now + timedelta(seconds=max(1, min(int(ttl_seconds), 300)))).isoformat(),
    )
    rows = _load(cwd)
    rows.append(asdict(ticket))
    _save(cwd, rows[-200:])
    return ticket


def consume_execution_ticket(cwd: str, action_kind: str, *, now_utc: datetime | None = None) -> dict:
    now = now_utc or _utc_now()
    rows = _load(cwd)
    selected = -1
    for index in range(len(rows) - 1, -1, -1):
        row = rows[index]
        if bool(row.get("consumed", False)) or str(row.get("action_kind", "")) != str(action_kind):
            continue
        try:
            expiry = datetime.fromisoformat(str(row.get("expires_at_utc", "")).replace("Z", "+00:00"))
        except ValueError:
            continue
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)
        if now > expiry.astimezone(timezone.utc):
            continue
        selected = index
        break
    if selected < 0:
        return {"ok": False, "reason": "execution_authority_ticket_missing_or_expired"}
    rows[selected]["consumed"] = True
    rows[selected]["consumed_at_utc"] = now.isoformat()
    ticket = dict(rows[selected])
    _save(cwd, rows)
    return {"ok": True, "ticket": ticket}
