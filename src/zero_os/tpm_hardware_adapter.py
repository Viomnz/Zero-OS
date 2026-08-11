from __future__ import annotations

from dataclasses import dataclass

from zero_os.hardware_attestation import HardwareAttestationBundle, PcrValue
from zero_os.tpm2_quote_parser import QuoteParseError, compute_selected_pcr_digest, parse_tpms_attest_quote_b64
from zero_os.tpm_event_log_adapter import EventLogRecord, compare_reconstructed_pcrs, reconstruct_event_log
from zero_os.tpm_quote_verifier import QuoteSignatureEvidence, verify_quote_signature


@dataclass(frozen=True)
class TpmAdapterInput:
    device_identity: str
    nonce: str
    quoted_pcrs: tuple[PcrValue, ...]
    quoted_pcr_composite_sha256: str
    measured_boot_root_sha256: str
    monotonic_counter: int
    secure_boot_enabled: bool
    measured_boot_enabled: bool
    quote_signature: QuoteSignatureEvidence
    event_log: tuple[EventLogRecord, ...]
    debug_interface_enabled: bool = False
    dma_protection_enabled: bool = False
    provenance: tuple[str, ...] = ()


@dataclass(frozen=True)
class TpmAdapterDecision:
    verified: bool
    status: str
    reasons: tuple[str, ...]
    bundle: HardwareAttestationBundle | None
    quote_signature_verified: bool
    quote_claims_verified: bool
    event_log_verified: bool
    authority_granted: bool = False
    boot_authority_granted: bool = False


def adapt_tpm_evidence(raw: TpmAdapterInput) -> TpmAdapterDecision:
    reasons: list[str] = []
    quote = verify_quote_signature(raw.quote_signature)
    if not quote.verified:
        reasons.extend(quote.reasons)

    parsed = None
    try:
        parsed = parse_tpms_attest_quote_b64(raw.quote_signature.quoted_message_b64)
    except QuoteParseError as exc:
        reasons.append(str(exc))

    quote_claims_verified = False
    if parsed is not None:
        expected_nonce = str(raw.nonce).encode("utf-8")
        if parsed.extra_data != expected_nonce:
            reasons.append("signed_quote_nonce_mismatch")
        try:
            selected_digest = compute_selected_pcr_digest(raw.quoted_pcrs, parsed.selected_pcr_indices)
            if selected_digest != parsed.pcr_digest_sha256:
                reasons.append("signed_quote_pcr_digest_mismatch")
            if str(raw.quoted_pcr_composite_sha256).lower() != parsed.pcr_digest_sha256:
                reasons.append("adapter_pcr_composite_not_signed_quote_digest")
        except QuoteParseError as exc:
            reasons.append(str(exc))
        quote_claims_verified = not any(
            reason in {
                "signed_quote_nonce_mismatch",
                "signed_quote_pcr_digest_mismatch",
                "adapter_pcr_composite_not_signed_quote_digest",
            }
            or reason.startswith("selected_pcr_")
            for reason in reasons
        )

    event = reconstruct_event_log(raw.event_log)
    if not event.verified:
        reasons.extend(event.reasons)
    reasons.extend(compare_reconstructed_pcrs(event.reconstructed_pcrs, raw.quoted_pcrs))
    if not raw.provenance:
        reasons.append("adapter_provenance_missing")
    if not raw.device_identity:
        reasons.append("device_identity_missing")
    if not raw.nonce:
        reasons.append("nonce_missing")

    if reasons:
        return TpmAdapterDecision(
            verified=False,
            status="TPM_ADAPTER_EVIDENCE_CONTESTED",
            reasons=tuple(dict.fromkeys(reasons)),
            bundle=None,
            quote_signature_verified=quote.verified,
            quote_claims_verified=quote_claims_verified,
            event_log_verified=event.verified,
            authority_granted=False,
            boot_authority_granted=False,
        )

    assert parsed is not None
    bundle = HardwareAttestationBundle(
        device_identity=raw.device_identity,
        attestation_key_id=quote.public_key_fingerprint,
        nonce=raw.nonce,
        quoted_pcrs=raw.quoted_pcrs,
        quoted_pcr_composite_sha256=parsed.pcr_digest_sha256,
        event_log_root_sha256=event.event_log_root_sha256,
        measured_boot_root_sha256=raw.measured_boot_root_sha256,
        monotonic_counter=int(raw.monotonic_counter),
        signature_verified=True,
        secure_boot_enabled=bool(raw.secure_boot_enabled),
        measured_boot_enabled=bool(raw.measured_boot_enabled),
        debug_interface_enabled=bool(raw.debug_interface_enabled),
        dma_protection_enabled=bool(raw.dma_protection_enabled),
        provenance=tuple(raw.provenance) + (
            "tpm_quote_signature_verified",
            "tpm_quote_nonce_bound",
            "tpm_quote_pcr_digest_bound",
            "event_log_reconstructed",
        ),
    )
    return TpmAdapterDecision(
        verified=True,
        status="TPM_ADAPTER_EVIDENCE_VERIFIED_IN_SCOPE",
        reasons=(),
        bundle=bundle,
        quote_signature_verified=True,
        quote_claims_verified=True,
        event_log_verified=True,
        authority_granted=False,
        boot_authority_granted=False,
    )


def adapter_invariants() -> tuple[str, ...]:
    return (
        "raw_tpm_evidence_is_not_boot_authority",
        "quote_signature_and_event_log_are_verified_independently",
        "signed_quote_must_bind_nonce_and_pcr_digest",
        "event_log_reconstruction_must_match_quoted_pcrs",
        "adapter_cannot_mint_zero_os_authority",
        "adapter_cannot_self_certify_hardware_identity",
    )
