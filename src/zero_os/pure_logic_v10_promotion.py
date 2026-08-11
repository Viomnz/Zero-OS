from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from zero_os.authority_issuer_boundary import IssuerBoundaryStatus, current_software_issuer_status
from zero_os.authority_runtime_integration_audit import audit_authority_runtime_integration
from zero_os.authority_runtime_trace import verify_trace_chain
from zero_os.path_law_authority_guard import audit_path_law_non_authority
from zero_os.security_control_plane import verify_history_chain
from zero_os.security_control_plane_audit import audit_security_control_plane


def evaluate_v10_promotion(
    root: str | Path,
    *,
    issuer_status: IssuerBoundaryStatus | None = None,
    representative_trace_certified: bool = False,
    ci_passed: bool = False,
    fresh_adversarial_audit_passed: bool = False,
    formal_illegal_state_check_passed: bool = False,
) -> dict:
    base = Path(root).resolve()
    integration = audit_authority_runtime_integration(base)
    security = audit_security_control_plane(base)
    path_law = audit_path_law_non_authority(base)
    trace_chain = verify_trace_chain(str(base))
    control_history = verify_history_chain(str(base))
    issuer = issuer_status or current_software_issuer_status()

    blockers: list[str] = []
    if not integration.get("promotion_permitted", False):
        blockers.append("authority_runtime_integration_failed")
    if not security.get("promotion_permitted", False):
        blockers.append("security_control_plane_incomplete")
    if not path_law.get("promotion_permitted", False):
        blockers.append("path_law_attempted_final_authority")
    if not trace_chain.get("ok", False):
        blockers.append("authority_trace_chain_invalid")
    if not control_history.get("ok", False):
        blockers.append("security_control_history_invalid")
    if not issuer.production_authority_permitted:
        blockers.append("issuer_privilege_domain_not_production_grade")
    if not representative_trace_certified:
        blockers.append("representative_end_to_end_authority_trace_missing")
    if not ci_passed:
        blockers.append("ci_not_passed")
    if not fresh_adversarial_audit_passed:
        blockers.append("fresh_adversarial_audit_missing")
    if not formal_illegal_state_check_passed:
        blockers.append("formal_illegal_state_check_missing")

    return {
        "promotion_permitted": not blockers,
        "status": "PROVISIONAL_PROMOTION_IN_DEMONSTRATED_SCOPE" if not blockers else "BLOCK_PROMOTION",
        "blockers": blockers,
        "authority_integration": integration,
        "security_control_plane": security,
        "path_law_non_authority": path_law,
        "authority_trace_chain": trace_chain,
        "security_control_history": control_history,
        "issuer_boundary": asdict(issuer),
        "representative_trace_certified": bool(representative_trace_certified),
        "ci_passed": bool(ci_passed),
        "fresh_adversarial_audit_passed": bool(fresh_adversarial_audit_passed),
        "formal_illegal_state_check_passed": bool(formal_illegal_state_check_passed),
        "discovery_confidence_can_override": False,
        "path_logic_can_grant_final_authority": False,
        "path_logic_role": "selection_only_after_independent_authority",
        "general_security_claim_permitted": False,
        "pure_logic_self_exemption_permitted": False,
    }
