from __future__ import annotations

from dataclasses import asdict, dataclass

from zero_os.protected_correction_plane import CorrectionCandidate, default_correction_plane


@dataclass(frozen=True)
class FirmwareRevisionRequest:
    candidate_id: str
    target: str
    proposer_id: str
    provenance: tuple[str, ...]
    invariant_checks: tuple[str, ...]
    pressure_results: tuple[str, ...]
    independent_evaluators: tuple[str, ...]
    rollback_reference: str
    canary_reference: str
    compatibility_reference: str
    signed_manifest_reference: str
    monotonic_version: int
    current_monotonic_version: int


def evaluate_firmware_revision(request: FirmwareRevisionRequest) -> dict:
    reasons: list[str] = []
    if request.target not in {
        "firmware_policy",
        "firmware_boot_manifest",
        "firmware_root_public_keys",
        "firmware_recovery_policy",
        "firmware_update_authority",
    }:
        reasons.append("target_not_firmware_revision_surface")
    if not request.signed_manifest_reference:
        reasons.append("signed_manifest_missing")
    if request.monotonic_version <= request.current_monotonic_version:
        reasons.append("rollback_or_non_monotonic_firmware_version")

    candidate = CorrectionCandidate(
        candidate_id=request.candidate_id,
        target=request.target,
        proposer_id=request.proposer_id,
        provenance=request.provenance,
        invariant_checks=request.invariant_checks,
        pressure_results=request.pressure_results,
        independent_evaluators=request.independent_evaluators,
        rollback_reference=request.rollback_reference,
        canary_reference=request.canary_reference,
        compatibility_reference=request.compatibility_reference,
    )
    correction = default_correction_plane().architecture_revision_allowed(candidate)
    if not correction.allowed:
        reasons.extend(correction.reasons)

    return {
        "allowed_for_isolated_firmware_update_path": not reasons,
        "reasons": reasons,
        "correction_decision": asdict(correction),
        "firmware_is_revision_capable": True,
        "runtime_direct_write_permitted": False,
        "path_logic_final_authority": False,
        "final_firmware_signature_authority_granted": False,
    }
