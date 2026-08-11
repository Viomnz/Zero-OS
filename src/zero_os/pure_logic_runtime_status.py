from __future__ import annotations

from pathlib import Path

from zero_os.authority_issuer_boundary import current_software_issuer_status
from zero_os.authority_runtime_integration_audit import audit_authority_runtime_integration
from zero_os.authority_runtime_trace import verify_trace_chain
from zero_os.path_law_authority_guard import audit_path_law_non_authority
from zero_os.security_control_plane import verify_history_chain
from zero_os.security_control_plane_audit import audit_security_control_plane


MASTER_LAWS = (
    "REALITY",
    "SURVIVAL",
    "INVESTIGATION",
    "PLURALITY",
    "PATH",
    "RESOURCE",
)


def pure_logic_runtime_status(root: str | Path) -> dict:
    """Return implementation evidence, not a self-certification of correctness."""
    base = Path(root).resolve()
    authority = audit_authority_runtime_integration(base)
    security = audit_security_control_plane(base)
    path_law = audit_path_law_non_authority(base)
    trace = verify_trace_chain(str(base))
    control_history = verify_history_chain(str(base))
    issuer = current_software_issuer_status()

    blockers: list[str] = []
    if not authority.get("promotion_permitted", False):
        blockers.append("authority_runtime_integration_incomplete")
    if not security.get("promotion_permitted", False):
        blockers.append("security_control_plane_incomplete")
    if not path_law.get("promotion_permitted", False):
        blockers.append("path_law_authority_violation")
    if not trace.get("ok", False):
        blockers.append("authority_runtime_trace_invalid")
    if not control_history.get("ok", False):
        blockers.append("security_control_history_invalid")
    if not issuer.production_authority_permitted:
        blockers.append("issuer_not_production_isolated")

    return {
        "framework": "Pure Logic / Zero AI",
        "master_laws": list(MASTER_LAWS),
        "logic_serves_reality": True,
        "self_certification_permitted": False,
        "status": "PROVISIONAL_IMPLEMENTATION_IN_IDENTIFIED_SCOPE" if not blockers else "IMPLEMENTED_WITH_BLOCKERS",
        "blockers": blockers,
        "authority_runtime": authority,
        "security_control_plane": security,
        "path_law_non_authority": path_law,
        "authority_trace_chain": trace,
        "security_control_history": control_history,
        "issuer_boundary": {
            "mode": issuer.mode,
            "separate_process": issuer.separate_process,
            "separate_os_identity": issuer.separate_os_identity,
            "private_key_unavailable_to_runtime": issuer.private_key_unavailable_to_runtime,
            "hardware_backed": issuer.hardware_backed,
            "production_authority_permitted": issuer.production_authority_permitted,
        },
        "claims": {
            "discovery_is_not_scope_authority": True,
            "memory_is_not_execution_authority": True,
            "path_logic_is_not_final_authority": True,
            "path_logic_role": "select_only_among_independently_authorized_surviving_paths",
            "objectives_have_separate_authority": True,
            "privileged_actions_require_scoped_authority": True,
            "security_controls_are_protected_policy": True,
            "authority_artifacts_are_attested": True,
            "runtime_authority_chain_is_traceable": True,
            "general_security_claim_permitted": False,
        },
        "unresolved_scope": [
            "same_privilege_hostile_runtime",
            "native_and_non_python_reachability",
            "hardware_firmware_and_side_channels",
            "formal_illegal_state_unreachability",
            "true_external_verifier_independence",
        ],
    }
