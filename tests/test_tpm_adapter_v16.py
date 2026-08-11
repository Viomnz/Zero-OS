from __future__ import annotations

import base64
import hashlib
import struct

import pytest

crypto = pytest.importorskip("cryptography")
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

from zero_os.hardware_attestation import HardwareAttestationPolicy, PcrValue, verify_hardware_attestation
from zero_os.tpm_event_log_adapter import EventLogRecord
from zero_os.tpm_hardware_adapter import TpmAdapterInput, adapt_tpm_evidence
from zero_os.tpm_quote_verifier import QuoteSignatureEvidence


def _extend(old_hex: str, event_digest_hex: str) -> str:
    return hashlib.sha256(bytes.fromhex(old_hex) + bytes.fromhex(event_digest_hex)).hexdigest()


def _build_quote(nonce: str, pcr_digest_hex: str) -> bytes:
    out = bytearray()
    out += struct.pack(">I", 0xFF544347)
    out += struct.pack(">H", 0x8018)
    out += struct.pack(">H", 0)  # qualifiedSigner
    extra = nonce.encode("utf-8")
    out += struct.pack(">H", len(extra)) + extra
    out += struct.pack(">QII", 0, 0, 0) + b"\x01"
    out += struct.pack(">Q", 1)
    out += struct.pack(">I", 1)  # one PCR selection
    out += struct.pack(">H", 0x000B)  # SHA256 bank
    out += b"\x03" + b"\x01\x00\x00"  # PCR 0
    digest = bytes.fromhex(pcr_digest_hex)
    out += struct.pack(">H", len(digest)) + digest
    return bytes(out)


def _fixture(nonce: str = "fresh-nonce"):
    event_digest = hashlib.sha256(b"boot-event").hexdigest()
    payload_digest = hashlib.sha256(b"payload").hexdigest()
    pcr0 = _extend("00" * 32, event_digest)
    pcr_digest = hashlib.sha256(bytes.fromhex(pcr0)).hexdigest()
    quote = _build_quote(nonce, pcr_digest)

    private_key = ec.generate_private_key(ec.SECP256R1())
    public_key = private_key.public_key()
    signature = private_key.sign(quote, ec.ECDSA(hashes.SHA256()))
    pem = public_key.public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode("utf-8")
    der = public_key.public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
    key_id = "sha256:" + hashlib.sha256(der).hexdigest()

    raw = TpmAdapterInput(
        device_identity="device-1",
        nonce=nonce,
        quoted_pcrs=(PcrValue(0, pcr0),),
        quoted_pcr_composite_sha256=pcr_digest,
        measured_boot_root_sha256=hashlib.sha256(b"measured-root").hexdigest(),
        monotonic_counter=7,
        secure_boot_enabled=True,
        measured_boot_enabled=True,
        quote_signature=QuoteSignatureEvidence(
            quoted_message_b64=base64.b64encode(quote).decode("ascii"),
            signature_b64=base64.b64encode(signature).decode("ascii"),
            attestation_public_key_pem=pem,
            algorithm="ecdsa_sha256",
            attestation_key_id=key_id,
        ),
        event_log=(EventLogRecord(0, 0, "EV_POST_CODE", event_digest, payload_digest),),
        dma_protection_enabled=True,
        provenance=("tpm2", "uefi_event_log"),
    )
    return raw, key_id


def test_valid_tpm_adapter_produces_evidence_not_authority():
    raw, key_id = _fixture()
    decision = adapt_tpm_evidence(raw)
    assert decision.verified is True
    assert decision.quote_signature_verified is True
    assert decision.quote_claims_verified is True
    assert decision.event_log_verified is True
    assert decision.authority_granted is False
    assert decision.boot_authority_granted is False
    assert decision.bundle is not None

    hardware = verify_hardware_attestation(
        decision.bundle,
        HardwareAttestationPolicy(
            expected_device_identity="device-1",
            expected_nonce="fresh-nonce",
            allowed_attestation_keys=(key_id,),
            required_pcr_indices=(0,),
            minimum_monotonic_counter=7,
            require_dma_protection=True,
        ),
    )
    assert hardware.verified is True
    assert hardware.authority_granted is False


def test_signed_quote_nonce_cannot_be_relabelled():
    raw, _ = _fixture("signed-nonce")
    forged = TpmAdapterInput(**{**raw.__dict__, "nonce": "different-nonce"})
    decision = adapt_tpm_evidence(forged)
    assert decision.verified is False
    assert "signed_quote_nonce_mismatch" in decision.reasons


def test_attestation_key_label_cannot_spoof_public_key_identity():
    raw, _ = _fixture()
    forged_signature = QuoteSignatureEvidence(**{**raw.quote_signature.__dict__, "attestation_key_id": "sha256:" + "00" * 32})
    forged = TpmAdapterInput(**{**raw.__dict__, "quote_signature": forged_signature})
    decision = adapt_tpm_evidence(forged)
    assert decision.verified is False
    assert "attestation_key_identity_mismatch" in decision.reasons


def test_event_log_must_reconstruct_quoted_pcr():
    raw, _ = _fixture()
    bad_event = EventLogRecord(0, 0, "EV_POST_CODE", hashlib.sha256(b"different").hexdigest(), hashlib.sha256(b"payload").hexdigest())
    forged = TpmAdapterInput(**{**raw.__dict__, "event_log": (bad_event,)})
    decision = adapt_tpm_evidence(forged)
    assert decision.verified is False
    assert "event_log_pcr_mismatch:0" in decision.reasons
