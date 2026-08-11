from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime, timezone

from zero_os.authority_root_of_trust import AuthorityAttestation, verify_attestation


@dataclass(frozen=True)
class CapabilityLease:
    principal_id: str
    scopes: frozenset[str]
    issued_at_utc: str
    expires_at_utc: str
    attestation: AuthorityAttestation
    source: str = "zero-os-authority-root-v8"

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


def issue_capability_lease(*args, **kwargs):
    """Legacy arbitrary minting is forbidden in v8."""
    raise PermissionError("capability leases may only be minted by the authority root issuer")


def lease_from_attestation(cwd: str, attestation: AuthorityAttestation) -> CapabilityLease:
    verified = verify_attestation(cwd, attestation)
    if not verified.get("ok", False):
        raise PermissionError(str(verified.get("reason", "authority attestation invalid")))
    if attestation.artifact_kind != "capability_lease":
        raise PermissionError("attestation is not a capability lease")
    return CapabilityLease(
        principal_id=attestation.principal_id,
        scopes=frozenset(attestation.scopes),
        issued_at_utc=attestation.issued_at_utc,
        expires_at_utc=attestation.expires_at_utc,
        attestation=attestation,
    )


@contextmanager
def capability_lease_context(lease: CapabilityLease):
    token = _ACTIVE_LEASE.set(lease)
    try:
        yield lease
    finally:
        _ACTIVE_LEASE.reset(token)


def require_scope(scope: str, *, cwd: str | None = None) -> dict:
    required = str(scope or "").strip()
    lease = current_capability_lease()
    if lease is None:
        return {"ok": False, "reason": "capability_lease_missing", "required_scope": required}
    if not lease.active():
        return {"ok": False, "reason": "capability_lease_expired", "required_scope": required}
    if cwd is not None:
        verified = verify_attestation(cwd, lease.attestation)
        if not verified.get("ok", False):
            return {"ok": False, "reason": str(verified.get("reason", "capability_attestation_invalid")), "required_scope": required}
    if required not in lease.scopes:
        return {
            "ok": False,
            "reason": "capability_scope_missing",
            "required_scope": required,
            "lease_scopes": sorted(lease.scopes),
        }
    return {"ok": True, "reason": "attested_capability_scope_present", "required_scope": required, "principal_id": lease.principal_id}
