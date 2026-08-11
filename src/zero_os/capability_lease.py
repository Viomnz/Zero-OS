from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable


@dataclass(frozen=True)
class CapabilityLease:
    principal_id: str
    scopes: frozenset[str]
    issued_at_utc: str
    expires_at_utc: str
    source: str = "pure_logic_capability_kernel"

    def active(self, now_utc: datetime | None = None) -> bool:
        now = now_utc or datetime.now(timezone.utc)
        try:
            expiry = datetime.fromisoformat(self.expires_at_utc.replace("Z", "+00:00"))
        except ValueError:
            return False
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)
        return now <= expiry.astimezone(timezone.utc)


_ACTIVE_LEASE: ContextVar[CapabilityLease | None] = ContextVar("zero_os_capability_lease", default=None)


def current_capability_lease() -> CapabilityLease | None:
    return _ACTIVE_LEASE.get()


def issue_capability_lease(principal_id: str, scopes: Iterable[str], *, ttl_seconds: int = 30) -> CapabilityLease:
    now = datetime.now(timezone.utc)
    ttl = max(1, min(int(ttl_seconds), 300))
    return CapabilityLease(
        principal_id=str(principal_id or "").strip(),
        scopes=frozenset(str(scope) for scope in scopes if str(scope)),
        issued_at_utc=now.isoformat(),
        expires_at_utc=(now + timedelta(seconds=ttl)).isoformat(),
    )


@contextmanager
def capability_lease_context(lease: CapabilityLease):
    token = _ACTIVE_LEASE.set(lease)
    try:
        yield lease
    finally:
        _ACTIVE_LEASE.reset(token)


def require_scope(scope: str) -> dict:
    required = str(scope or "").strip()
    lease = current_capability_lease()
    if lease is None:
        return {"ok": False, "reason": "capability_lease_missing", "required_scope": required}
    if not lease.active():
        return {"ok": False, "reason": "capability_lease_expired", "required_scope": required}
    if required not in lease.scopes:
        return {
            "ok": False,
            "reason": "capability_scope_missing",
            "required_scope": required,
            "lease_scopes": sorted(lease.scopes),
        }
    return {"ok": True, "reason": "capability_scope_present", "required_scope": required, "principal_id": lease.principal_id}
