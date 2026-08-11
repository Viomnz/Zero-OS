from __future__ import annotations

import base64
import json
import os
import secrets
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable
from uuid import uuid4

from zero_os.authority_ledger import AuthorityLedger
from zero_os.authority_runtime_trace import record_event
from zero_os.objective_authority import ObjectiveAuthorityLedger
from zero_os.pure_logic_authority_kernel import ConstitutionalRequest, decide as constitutional_decide
from zero_os.resource_law_budget import VerificationBudget

ISSUER_ID = "zero-os-authority-root-v12-ed25519"
SCHEMA_VERSION = 2

try:
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    _ED25519_AVAILABLE = True
except Exception:
    InvalidSignature = Exception
    serialization = None
    Ed25519PrivateKey = None
    _ED25519_AVAILABLE = False


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


def _private_path(cwd: str) -> Path:
    return _root_dir(cwd) / "issuer_ed25519_private.pem"


def _public_path(cwd: str) -> Path:
    return _root_dir(cwd) / "issuer_ed25519_public.pem"


def asymmetric_crypto_available() -> bool:
    return bool(_ED25519_AVAILABLE)


def _ensure_keypair(cwd: str) -> None:
    if not _ED25519_AVAILABLE:
        raise RuntimeError("ed25519_backend_unavailable")
    private_path = _private_path(cwd)
    public_path = _public_path(cwd)
    if private_path.exists() and public_path.exists():
        return
    private = Ed25519PrivateKey.generate()
    public = private.public_key()
    private_path.write_bytes(private.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    public_path.write_bytes(public.public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo))
    try:
        os.chmod(private_path, 0o600)
        os.chmod(public_path, 0o644)
    except OSError:
        pass


def _private_key(cwd: str):
    _ensure_keypair(cwd)
    return serialization.load_pem_private_key(_private_path(cwd).read_bytes(), password=None)


def _public_key(cwd: str):
    if not _ED25519_AVAILABLE:
        raise RuntimeError("ed25519_backend_unavailable")
    if not _public_path(cwd).exists():
        _ensure_keypair(cwd)
    return serialization.load_pem_public_key(_public_path(cwd).read_bytes())


def public_verifier_pem(cwd: str) -> bytes:
    if not _public_path(cwd).exists():
        _ensure_keypair(cwd)
    return _public_path(cwd).read_bytes()


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
    if not _ED25519_AVAILABLE:
        return {"ok": False, "reason": "ed25519_backend_unavailable"}
    try:
        signature = base64.b64decode(str(attestation.signature or ""), validate=True)
        _public_key(cwd).verify(signature, _canonical(attestation.unsigned_payload()))
    except (ValueError, InvalidSignature, RuntimeError):
        return {"ok": False, "reason": "authority_attestation_signature_invalid"}
    try:
        expires = datetime.fromisoformat(attestation.expires_at_utc.replace("Z", "+00:00"))
    except ValueError:
        return {"ok": False, "reason": "authority_attestation_expiry_invalid"}
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if (now_utc or _utc_now()) > expires.astimezone(timezone.utc):
        return {"ok": False, "reason": "authority_attestation_expired"}
    if attestation.constitutional_status != "PROVISIONAL_SCOPED_AUTHORITY":
        return {"ok": False, "reason": "authority_attestation_constitutional_status_invalid"}
    return {"ok": True, "reason": "authority_attestation_verified", "issuer_id": attestation.issuer_id, "signature_scheme": "Ed25519"}


def issue_attestation_from_constitution(
    cwd: str,
    *,
    artifact_kind: str,
    constitutional_request: ConstitutionalRequest,
    authority_ledger: AuthorityLedger,
    objective_ledger: ObjectiveAuthorityLedger,
    verification_budget: VerificationBudget,
    active_dependency_ids: Iterable[str],
    subject_id: str,
    state_revision: str,
    scopes: Iterable[str],
    correction_plane_allows: bool = True,
    legal_state_ok: bool = True,
    ttl_seconds: int = 30,
) -> tuple[AuthorityAttestation, object]:
    if not _ED25519_AVAILABLE:
        raise RuntimeError("ed25519_backend_unavailable")
    decision = constitutional_decide(
        request=constitutional_request,
        authority_ledger=authority_ledger,
        objective_ledger=objective_ledger,
        budget=verification_budget,
        active_dependency_ids=active_dependency_ids,
        correction_plane_allows=correction_plane_allows,
        legal_state_ok=legal_state_ok,
    )
    if not decision.allowed:
        raise PermissionError("constitutional authority denied by root issuer")
    requested_scopes = tuple(sorted({str(x) for x in scopes if str(x)}))
    if constitutional_request.action_scope not in requested_scopes:
        raise PermissionError("issuer scope does not contain constitutional action scope")
    now = _utc_now()
    ttl = max(1, min(int(ttl_seconds), 300))
    artifact_id = str(uuid4())
    unsigned = {
        "schema_version": SCHEMA_VERSION,
        "issuer_id": ISSUER_ID,
        "artifact_kind": str(artifact_kind),
        "artifact_id": artifact_id,
        "principal_id": constitutional_request.actor.principal_id,
        "authority_id": constitutional_request.authority_id,
        "objective_id": constitutional_request.objective_id,
        "action_kind": constitutional_request.requested_capability,
        "subject_id": str(subject_id),
        "state_revision": str(state_revision),
        "scopes": requested_scopes,
        "issued_at_utc": now.isoformat(),
        "expires_at_utc": (now + timedelta(seconds=ttl)).isoformat(),
        "nonce": secrets.token_hex(16),
        "constitutional_status": decision.status,
    }
    signature = base64.b64encode(_private_key(cwd).sign(_canonical(unsigned))).decode("ascii")
    attestation = AuthorityAttestation(**unsigned, signature=signature)
    binding = {"verification_depth": decision.verification_depth, "required_evidence_groups": decision.required_evidence_groups, "scopes": list(requested_scopes), "artifact_kind": artifact_kind}
    record_event(cwd, trace_id=artifact_id, event_kind="constitutional_decision", principal_id=attestation.principal_id, authority_id=attestation.authority_id, objective_id=attestation.objective_id, action_kind=attestation.action_kind, subject_id=attestation.subject_id, state_revision=attestation.state_revision, artifact_id=artifact_id, payload={**binding, "status": decision.status})
    record_event(cwd, trace_id=artifact_id, event_kind="issuer_attestation", principal_id=attestation.principal_id, authority_id=attestation.authority_id, objective_id=attestation.objective_id, action_kind=attestation.action_kind, subject_id=attestation.subject_id, state_revision=attestation.state_revision, artifact_id=artifact_id, payload={**binding, "issuer_id": attestation.issuer_id, "signature_scheme": "Ed25519", "expires_at_utc": attestation.expires_at_utc})
    return attestation, decision
