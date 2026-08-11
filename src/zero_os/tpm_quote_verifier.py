from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import Literal

try:
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec, padding, rsa
    _CRYPTO_AVAILABLE = True
except Exception:  # pragma: no cover - deployment dependency
    _CRYPTO_AVAILABLE = False


@dataclass(frozen=True)
class QuoteSignatureEvidence:
    quoted_message_b64: str
    signature_b64: str
    attestation_public_key_pem: str
    algorithm: Literal["rsa_pss_sha256", "rsa_pkcs1v15_sha256", "ecdsa_sha256"]
    attestation_key_id: str


@dataclass(frozen=True)
class QuoteSignatureDecision:
    verified: bool
    status: str
    reasons: tuple[str, ...]
    attestation_key_id: str
    authority_granted: bool = False


def crypto_available() -> bool:
    return bool(_CRYPTO_AVAILABLE)


def verify_quote_signature(evidence: QuoteSignatureEvidence) -> QuoteSignatureDecision:
    reasons: list[str] = []
    if not _CRYPTO_AVAILABLE:
        reasons.append("cryptographic_backend_unavailable")
        return QuoteSignatureDecision(False, "QUOTE_SIGNATURE_CONTESTED", tuple(reasons), evidence.attestation_key_id)
    if not evidence.attestation_key_id:
        reasons.append("attestation_key_id_missing")
    try:
        message = base64.b64decode(evidence.quoted_message_b64, validate=True)
        signature = base64.b64decode(evidence.signature_b64, validate=True)
    except Exception:
        reasons.append("quote_or_signature_base64_invalid")
        return QuoteSignatureDecision(False, "QUOTE_SIGNATURE_CONTESTED", tuple(reasons), evidence.attestation_key_id)
    if not message:
        reasons.append("quoted_message_missing")
    if not signature:
        reasons.append("quote_signature_missing")
    try:
        public_key = serialization.load_pem_public_key(evidence.attestation_public_key_pem.encode("utf-8"))
    except Exception:
        reasons.append("attestation_public_key_invalid")
        return QuoteSignatureDecision(False, "QUOTE_SIGNATURE_CONTESTED", tuple(reasons), evidence.attestation_key_id)

    if not reasons:
        try:
            if evidence.algorithm == "rsa_pss_sha256":
                if not isinstance(public_key, rsa.RSAPublicKey):
                    raise TypeError("rsa_key_required")
                public_key.verify(signature, message, padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH), hashes.SHA256())
            elif evidence.algorithm == "rsa_pkcs1v15_sha256":
                if not isinstance(public_key, rsa.RSAPublicKey):
                    raise TypeError("rsa_key_required")
                public_key.verify(signature, message, padding.PKCS1v15(), hashes.SHA256())
            elif evidence.algorithm == "ecdsa_sha256":
                if not isinstance(public_key, ec.EllipticCurvePublicKey):
                    raise TypeError("ec_key_required")
                public_key.verify(signature, message, ec.ECDSA(hashes.SHA256()))
            else:
                reasons.append("unsupported_quote_signature_algorithm")
        except Exception:
            reasons.append("quote_signature_invalid")

    return QuoteSignatureDecision(
        verified=not reasons,
        status="QUOTE_SIGNATURE_VERIFIED" if not reasons else "QUOTE_SIGNATURE_CONTESTED",
        reasons=tuple(reasons),
        attestation_key_id=evidence.attestation_key_id,
        authority_granted=False,
    )
