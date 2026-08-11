from __future__ import annotations

import ast
from pathlib import Path


_REQUIRED_FILES = (
    "src/zero_os/firmware_pure_logic.py",
    "src/zero_os/firmware_reality_checkpoint.py",
    "src/zero_os/kernel_rnd/boot_trust.py",
    "src/zero_os/protected_correction_plane.py",
)

_FORBIDDEN_AUTHORITY_NAMES = {
    "issue_attestation_from_constitution",
    "ticket_from_attestation",
    "lease_from_attestation",
    "authorize_and_issue_execution_ticket",
}

_REQUIRED_INVARIANT_TEXT = (
    "path_logic_never_grants_boot_or_firmware_authority",
    "firmware_is_protected_but_revision_capable",
    "firmware_cannot certify its own correctness",
)


def _call_name(node: ast.Call) -> str:
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return ""


def audit_firmware_integration(root: str | Path) -> dict:
    base = Path(root).resolve()
    findings: list[dict] = []

    for rel in _REQUIRED_FILES:
        path = base / rel
        if not path.exists():
            findings.append({"path": rel, "line": 0, "reason": "required_firmware_boundary_missing"})

    kernel = base / "src/zero_os/firmware_pure_logic.py"
    if kernel.exists():
        try:
            text = kernel.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(text)
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and _call_name(node) in _FORBIDDEN_AUTHORITY_NAMES:
                    findings.append({"path": str(kernel.relative_to(base)), "line": int(getattr(node, "lineno", 0)), "reason": "firmware_layer_attempted_to_mint_os_final_authority"})
            for required in _REQUIRED_INVARIANT_TEXT:
                if required not in text:
                    findings.append({"path": str(kernel.relative_to(base)), "line": 0, "reason": f"firmware_invariant_missing:{required}"})
        except (OSError, SyntaxError):
            findings.append({"path": str(kernel.relative_to(base)), "line": 0, "reason": "firmware_kernel_unparseable"})

    correction = base / "src/zero_os/protected_correction_plane.py"
    if correction.exists():
        text = correction.read_text(encoding="utf-8", errors="replace")
        for target in (
            "firmware_policy",
            "firmware_boot_manifest",
            "firmware_root_public_keys",
            "firmware_rollback_counter",
            "firmware_recovery_policy",
            "firmware_reality_checkpoint",
            "firmware_update_authority",
        ):
            if target not in text:
                findings.append({"path": str(correction.relative_to(base)), "line": 0, "reason": f"firmware_protected_target_missing:{target}"})

    return {
        "ok": not findings,
        "promotion_permitted": not findings,
        "status": "PURE_LOGIC_FIRMWARE_STATIC_SCOPE_READY" if not findings else "BLOCK_PROMOTION",
        "findings": findings,
        "finding_count": len(findings),
        "limitations": [
            "static integration is not hardware attestation",
            "TPM Secure Enclave HSM provisioning requires deployment evidence",
            "firmware implementation outside Python requires separate native audit",
            "hardware and firmware supply chain remain outside demonstrated scope",
        ],
        "path_logic_final_authority": False,
        "firmware_self_certification_permitted": False,
    }
