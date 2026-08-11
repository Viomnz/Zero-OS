from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from zero_os.authority_issuer_boundary import IssuerBoundaryStatus, current_software_issuer_status
from zero_os.authority_runtime_integration_audit import audit_authority_runtime_integration
from zero_os.security_control_plane_audit import audit_security_control_plane


def evaluate_v9_promotion(
    root: str | Path,
    *,
    issuer_status: IssuerBoundaryStatus | None = None,
    runtime_trace_certified: bool = False,
    ci_passed: bool = False,
    fresh_adversarial_audit_passed: bool = False,
) -> dict:
    integration = audit_authority_runtime_integration(root)
    security = audit_security_control_plane(root)
    issuer = issuer_status or current_software_issuer_status()

    blockers: list[str] = []
    if not integration.get("promotion_permitted", False):
        blockers.append("authority_runtime_integration_failed")
    if not security.get("promotion_permitted", False):
        blockers.append("security_control_plane_incomplete")
    if not issuer.production_authority_permitted:
        blockers.append("issuer_privilege_domain_not_production_grade")
    if not runtime_trace_certified:
        blockers.append("runtime_authority_trace_not_certified")
    if not ci_passed:
        blockers.append("ci_not_passed")
    if not fresh_adversarial_audit_passed:
        blockers.append("fresh_adversarial_audit_missing")

    return {
        "promotion_permitted": not blockers,
        "status": "PROVISIONAL_PROMOTION_IN_DEMONSTRATED_SCOPE" if not blockers else "BLOCK_PROMOTION",
        "blockers": blockers,
        "authority_integration": integration,
        "security_control_plane": security,
        "issuer_boundary": asdict(issuer),
        "runtime_trace_certified": bool(runtime_trace_certified),
        "ci_passed": bool(ci_passed),
        "fresh_adversarial_audit_passed": bool(fresh_adversarial_audit_passed),
        "general_security_claim_permitted": False,
    }
