from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable
from uuid import uuid4


ISSUER_ID = "zero-os-authority-root-v8"
SCHEMA_VERSION = 1


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _root_dir(cwd: str) -> Path:
    path = Path(cwd).resolve() / ".zero_os" / "authority_root"
    path.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(path, 0o700)
    except OSError:
        pass
    return path


def _secret_path(cwd: str) -> Path:
    return _root_dir(cwd) / "issuer.key"


def _issuer_secret(cwd: str) -> bytes:
    path = _secret_path(cwd)
    if not path.exists():
        path.write_bytes(secrets.token_bytes(32))
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
    data = path.read_bytes()
    if len(data) < 32:
        raise RuntimeError("authority issuer secret is invalid")
    return data


def _canonical(payload: dict) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


@dataclass(frozen=True)
class AuthorityAttestation:
    schema_version: int
    issuer_id: str
    artifact_kind: str
    artifact_id: str
    principal_id: str
    authority_id: str
    objective_id: str
    action_kind: str
    subject_id: str
    state_revision: str
    scopes: tuple[str, ...]
    issued_at_utc: str
    expires_at_utc: str
    nonce: str
    constitutional_status: str
    signature: str

    def unsigned_payload(self) -> dict:
        data = asdict(self)
        data.pop("signature", None)
        return data


def verify_attestation(cwd: str, attestation: AuthorityAttestation, *, now_utc: datetime | None = None) -> dict:
    if attestation.schema_version != SCHEMA_VERSION or attestation.issuer_id != ISSUER_ID:
        return {"ok": False, "reason": "authority_attestation_wrong_issuer_or_schema"}
    expected = hmac.new(_issuer_secret(cwd), _canonical(attestation.unsigned_payload()), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, str(attestation.signature or "")):
        return {"ok": False, "reason": "authority_attestation_signature_invalid"}
    try:
        expires = datetime.fromisoformat(attestation.expires_at_utc.replace("Z", "+00:00"))
    except ValueError:
        return {"ok": False, "reason": "authority_attestation_expiry_invalid"}
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if (now_utc or _utc_now()) > expires.astimezone(timezone.utc):
        return {"ok": False, "reason": "authority_attestation_expired"}
    if attestation.constitutional_status not in {"AUTHORIZED", "ALLOW", "SURVIVED_IN_SCOPE"}:
        return {"ok": False, "reason": "authority_attestation_constitutional_status_invalid"}
    return {"ok": True, "reason": "authority_attestation_verified", "issuer_id": attestation.issuer_id}


def issue_attestation(
    cwd: str,
    *,
    artifact_kind: str,
    principal_id: str,
    authority_id: str,
    objective_id: str,
    action_kind: str,
    subject_id: str,
    state_revision: str,
    scopes: Iterable[str],
    constitutional_allowed: bool,
    constitutional_status: str,
    ttl_seconds: int = 30,
) -> AuthorityAttestation:
    """Privileged software issuer boundary.

    Callers must arrive here only after the Pure Logic constitutional decision has
    survived. This function refuses to attest a denied decision. Sinks verify the
    resulting HMAC over every authority-bearing field rather than trusting object
    presence. The issuer secret is random and mode-restricted, but same-privilege
    hostile code remains outside the demonstrated trust scope until process/hardware
    isolation exists.
    """
    if not constitutional_allowed:
        raise PermissionError("constitutional authority denied")
    now = _utc_now()
    ttl = max(1, min(int(ttl_seconds), 300))
    unsigned = {
        "schema_version": SCHEMA_VERSION,
        "issuer_id": ISSUER_ID,
        "artifact_kind": str(artifact_kind),
        "artifact_id": str(uuid4()),
        "principal_id": str(principal_id),
        "authority_id": str(authority_id),
        "objective_id": str(objective_id),
        "action_kind": str(action_kind),
        "subject_id": str(subject_id),
        "state_revision": str(state_revision),
        "scopes": tuple(sorted({str(x) for x in scopes if str(x)})),
        "issued_at_utc": now.isoformat(),
        "expires_at_utc": (now + timedelta(seconds=ttl)).isoformat(),
        "nonce": secrets.token_hex(16),
        "constitutional_status": str(constitutional_status or "AUTHORIZED"),
    }
    signature = hmac.new(_issuer_secret(cwd), _canonical(unsigned), hashlib.sha256).hexdigest()
    return AuthorityAttestation(**unsigned, signature=signature)
