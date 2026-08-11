from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from zero_os.authority_issuer_boundary import IssuerBoundaryStatus
from zero_os.authority_root_of_trust import asymmetric_crypto_available
from zero_os.authority_runtime_integration_audit import audit_authority_runtime_integration
from zero_os.authority_runtime_trace import verify_trace_chain
from zero_os.control_loop_integration_audit import audit_control_loop_integration
from zero_os.external_authority_issuer import assess_external_issuer
from zero_os.firmware_integration_audit import audit_firmware_integration
from zero_os.formal_authority_model_check import model_check_authority_state_machine
from zero_os.path_law_semantic_guard import audit_path_law_semantic_non_authority
from zero_os.security_control_plane import verify_history_chain
from zero_os.security_control_plane_audit import audit_security_control_plane


def evaluate_v10_promotion(
    root: str | Path,
    *,
    issuer_status: IssuerBoundaryStatus | None = None,
    representative_trace_certified: bool = False,
    external_history_witness_verified: bool = False,
    firmware_hardware_attestation_verified: bool = False,
    firmware_external_checkpoint_verified: bool = False,
    ci_passed: bool = False,
    fresh_adversarial_audit_passed: bool = False,
) -> dict:
    base = Path(root).resolve()
    integration = audit_authority_runtime_integration(base)
    security = audit_security_control_plane(base)
    path_law = audit_path_law_semantic_non_authority(base)
    control_loops = audit_control_loop_integration(base)
    firmware = audit_firmware_integration(base)
    trace_chain = verify_trace_chain(str(base))
    control_history = verify_history_chain(str(base))
    issuer = issuer_status or assess_external_issuer(str(base))
    asymmetric_root = asymmetric_crypto_available()
    formal_model = model_check_authority_state_machine()

    blockers: list[str] = []
    if not integration.get("promotion_permitted", False): blockers.append("authority_runtime_integration_failed")
    if not security.get("promotion_permitted", False): blockers.append("security_control_plane_incomplete")
    if not path_law.get("promotion_permitted", False): blockers.append("path_law_semantic_authority_reachability")
    if not control_loops.get("promotion_permitted", False): blockers.append("autonomous_control_loop_authority_integration_incomplete")
    if not firmware.get("promotion_permitted", False): blockers.append("pure_logic_firmware_static_integration_incomplete")
    if not trace_chain.get("ok", False): blockers.append("authority_trace_chain_invalid")
    if not control_history.get("ok", False): blockers.append("security_control_history_invalid")
    if not asymmetric_root: blockers.append("asymmetric_authority_root_unavailable")
    if not external_history_witness_verified: blockers.append("external_history_witness_missing")
    if not firmware_hardware_attestation_verified: blockers.append("firmware_hardware_attestation_missing")
    if not firmware_external_checkpoint_verified: blockers.append("firmware_external_checkpoint_missing")
    if not issuer.production_authority_permitted: blockers.append("issuer_privilege_domain_not_production_grade")
    if not formal_model.get("ok", False): blockers.append("formal_authority_state_model_failed")
    if not representative_trace_certified: blockers.append("representative_end_to_end_authority_trace_missing")
    if not ci_passed: blockers.append("ci_not_passed")
    if not fresh_adversarial_audit_passed: blockers.append("fresh_adversarial_audit_missing")

    return {
        "promotion_permitted": not blockers,
        "status": "PROVISIONAL_PROMOTION_IN_DEMONSTRATED_SCOPE" if not blockers else "BLOCK_PROMOTION",
        "blockers": blockers,
        "authority_integration": integration,
        "security_control_plane": security,
        "path_law_non_authority": path_law,
        "control_loop_authority": control_loops,
        "firmware_authority": firmware,
        "authority_trace_chain": trace_chain,
        "security_control_history": control_history,
        "asymmetric_authority_root_available": asymmetric_root,
        "external_history_witness_verified": bool(external_history_witness_verified),
        "firmware_hardware_attestation_verified": bool(firmware_hardware_attestation_verified),
        "firmware_external_checkpoint_verified": bool(firmware_external_checkpoint_verified),
        "issuer_boundary": asdict(issuer),
        "formal_authority_state_model": formal_model,
        "representative_trace_certified": bool(representative_trace_certified),
        "ci_passed": bool(ci_passed),
        "fresh_adversarial_audit_passed": bool(fresh_adversarial_audit_passed),
        "discovery_confidence_can_override": False,
        "path_logic_can_grant_final_authority": False,
        "path_logic_role": "selection_only_after_independent_authority",
        "control_loop_can_mint_final_authority": False,
        "controller_uncertainty_can_expand_irreversible_authority": False,
        "firmware_measurement_can_grant_final_authority": False,
        "firmware_self_certification_permitted": False,
        "general_security_claim_permitted": False,
        "pure_logic_self_exemption_permitted": False,
    }
