from __future__ import annotations

import base64
import hashlib
import struct
from dataclasses import dataclass
from typing import Iterable

from zero_os.hardware_attestation import PcrValue

TPM_GENERATED_VALUE = 0xFF544347
TPM_ST_ATTEST_QUOTE = 0x8018
TPM_ALG_SHA256 = 0x000B


class QuoteParseError(ValueError):
    pass


@dataclass(frozen=True)
class ParsedTpmQuote:
    magic: int
    attestation_type: int
    extra_data: bytes
    selected_pcr_indices: tuple[int, ...]
    pcr_digest_sha256: str
    firmware_version: int


def _take(data: bytes, offset: int, length: int) -> tuple[bytes, int]:
    end = offset + length
    if length < 0 or end > len(data):
        raise QuoteParseError("quote_truncated")
    return data[offset:end], end


def _u16(data: bytes, offset: int) -> tuple[int, int]:
    raw, offset = _take(data, offset, 2)
    return struct.unpack(">H", raw)[0], offset


def _u32(data: bytes, offset: int) -> tuple[int, int]:
    raw, offset = _take(data, offset, 4)
    return struct.unpack(">I", raw)[0], offset


def _u64(data: bytes, offset: int) -> tuple[int, int]:
    raw, offset = _take(data, offset, 8)
    return struct.unpack(">Q", raw)[0], offset


def _tpm2b(data: bytes, offset: int) -> tuple[bytes, int]:
    size, offset = _u16(data, offset)
    return _take(data, offset, size)


def parse_tpms_attest_quote_b64(quoted_message_b64: str) -> ParsedTpmQuote:
    try:
        data = base64.b64decode(quoted_message_b64, validate=True)
    except Exception as exc:
        raise QuoteParseError("quoted_message_base64_invalid") from exc
    offset = 0
    magic, offset = _u32(data, offset)
    attestation_type, offset = _u16(data, offset)
    if magic != TPM_GENERATED_VALUE:
        raise QuoteParseError("tpm_magic_invalid")
    if attestation_type != TPM_ST_ATTEST_QUOTE:
        raise QuoteParseError("tpm_attestation_type_not_quote")

    _qualified_signer, offset = _tpm2b(data, offset)
    extra_data, offset = _tpm2b(data, offset)

    _clock, offset = _u64(data, offset)
    _reset_count, offset = _u32(data, offset)
    _restart_count, offset = _u32(data, offset)
    _safe, offset = _take(data, offset, 1)
    firmware_version, offset = _u64(data, offset)

    selection_count, offset = _u32(data, offset)
    if selection_count <= 0 or selection_count > 16:
        raise QuoteParseError("pcr_selection_count_invalid")
    selected: list[int] = []
    for _ in range(selection_count):
        hash_alg, offset = _u16(data, offset)
        size_raw, offset = _take(data, offset, 1)
        sizeof_select = size_raw[0]
        bitmap, offset = _take(data, offset, sizeof_select)
        if hash_alg != TPM_ALG_SHA256:
            raise QuoteParseError("unsupported_pcr_bank_algorithm")
        for byte_index, byte_value in enumerate(bitmap):
            for bit in range(8):
                if byte_value & (1 << bit):
                    selected.append(byte_index * 8 + bit)

    pcr_digest, offset = _tpm2b(data, offset)
    if len(pcr_digest) != 32:
        raise QuoteParseError("quote_pcr_digest_not_sha256")
    if offset != len(data):
        raise QuoteParseError("quote_trailing_bytes")
    return ParsedTpmQuote(
        magic=magic,
        attestation_type=attestation_type,
        extra_data=extra_data,
        selected_pcr_indices=tuple(sorted(set(selected))),
        pcr_digest_sha256=pcr_digest.hex(),
        firmware_version=firmware_version,
    )


def compute_selected_pcr_digest(rows: Iterable[PcrValue], selected_indices: Iterable[int]) -> str:
    pcr_map = {int(row.index): str(row.digest_sha256).lower() for row in rows}
    selected = tuple(sorted(set(int(index) for index in selected_indices)))
    if not selected:
        raise QuoteParseError("selected_pcrs_empty")
    parts: list[bytes] = []
    for index in selected:
        digest = pcr_map.get(index, "")
        if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
            raise QuoteParseError(f"selected_pcr_missing_or_invalid:{index}")
        parts.append(bytes.fromhex(digest))
    return hashlib.sha256(b"".join(parts)).hexdigest()
