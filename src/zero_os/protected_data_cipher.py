from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    _AESGCM_AVAILABLE = True
except Exception:
    AESGCM = None
    _AESGCM_AVAILABLE = False

SCHEMA_VERSION = 1


def crypto_available() -> bool:
    return bool(_AESGCM_AVAILABLE)


@dataclass(frozen=True)
class EncryptedProtectedData:
    schema_version: int
    data_id: str
    content_revision: str
    key_id: str
    nonce_b64: str
    ciphertext_b64: str
    aad_b64: str

    def to_json(self) -> str:
        return json.dumps(self.__dict__, sort_keys=True, separators=(",", ":"))

    @classmethod
    def from_json(cls, raw: str) -> "EncryptedProtectedData":
        data = json.loads(raw)
        return cls(**data)


def _aad(data_id: str, content_revision: str, key_id: str) -> bytes:
    return json.dumps(
        {"schema_version": SCHEMA_VERSION, "data_id": str(data_id), "content_revision": str(content_revision), "key_id": str(key_id)},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def encrypt_bytes(*, data_id: str, content_revision: str, key_id: str, plaintext: bytes, data_key: bytes) -> EncryptedProtectedData:
    if not _AESGCM_AVAILABLE:
        raise RuntimeError("aesgcm_backend_unavailable")
    if len(data_key) not in {16, 24, 32}:
        raise ValueError("invalid_aes_key_length")
    nonce = os.urandom(12)
    aad = _aad(data_id, content_revision, key_id)
    ciphertext = AESGCM(data_key).encrypt(nonce, bytes(plaintext), aad)
    return EncryptedProtectedData(
        schema_version=SCHEMA_VERSION,
        data_id=str(data_id),
        content_revision=str(content_revision),
        key_id=str(key_id),
        nonce_b64=base64.b64encode(nonce).decode("ascii"),
        ciphertext_b64=base64.b64encode(ciphertext).decode("ascii"),
        aad_b64=base64.b64encode(aad).decode("ascii"),
    )


def decrypt_bytes(container: EncryptedProtectedData, *, data_key: bytes, expected_data_id: str, expected_revision: str, expected_key_id: str) -> bytes:
    if not _AESGCM_AVAILABLE:
        raise RuntimeError("aesgcm_backend_unavailable")
    if container.schema_version != SCHEMA_VERSION:
        raise PermissionError("protected_data_cipher_schema_mismatch")
    if container.data_id != str(expected_data_id) or container.content_revision != str(expected_revision) or container.key_id != str(expected_key_id):
        raise PermissionError("protected_data_cipher_binding_mismatch")
    aad = _aad(expected_data_id, expected_revision, expected_key_id)
    if base64.b64decode(container.aad_b64) != aad:
        raise PermissionError("protected_data_cipher_aad_mismatch")
    nonce = base64.b64decode(container.nonce_b64)
    ciphertext = base64.b64decode(container.ciphertext_b64)
    return AESGCM(data_key).decrypt(nonce, ciphertext, aad)
