from __future__ import annotations

import ast
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class SecurityControlFinding:
    finding_id: str
    path: str
    severity: str
    resolved: bool
    evidence: str

    def to_dict(self) -> dict:
        return asdict(self)


def _source(path: Path) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
        ast.parse(text)
        return text
    except (OSError, SyntaxError):
        return ""


def audit_security_control_plane(root: str | Path) -> dict:
    base = Path(root).resolve()
    antivirus = _source(base / "src/zero_os/antivirus.py")
    control = _source(base / "src/zero_os/security_control_plane.py")
    signing = _source(base / "src/zero_os/security_signing.py")
    correction = _source(base / "src/zero_os/protected_correction_plane.py")
    findings: list[SecurityControlFinding] = []

    deterministic_feed_key = "hashlib.sha256(str(key_path).encode" in antivirus
    findings.append(SecurityControlFinding(
        "legacy_antivirus_deterministic_feed_key",
        "src/zero_os/antivirus.py",
        "critical",
        not deterministic_feed_key,
        "legacy _feed_key must not derive signing material from a predictable path",
    ))

    legacy_policy_mutators = all(name in antivirus for name in ("def policy_set", "def suppression_add", "def suppression_remove"))
    legacy_has_authority_handoff = "acknowledge_consumed_execution_ticket" in antivirus or "mutate_state(" in antivirus or "mutate_batch(" in antivirus
    findings.append(SecurityControlFinding(
        "legacy_antivirus_control_mutators_mediated",
        "src/zero_os/antivirus.py",
        "critical",
        (not legacy_policy_mutators) or legacy_has_authority_handoff,
        "policy and suppression mutation must be mediated by the protected security control plane",
    ))

    findings.append(SecurityControlFinding(
        "security_control_plane_requires_runtime_handoff",
        "src/zero_os/security_control_plane.py",
        "critical",
        "acknowledge_consumed_execution_ticket" in control and "policy_change" in control,
        "control-plane state mutation consumes constitution-authorized policy_change handoff",
    ))
    findings.append(SecurityControlFinding(
        "feed_signing_uses_random_control_key",
        "src/zero_os/security_signing.py",
        "critical",
        "control_key(" in signing and "key_generation" in signing and "feed_rollback_detected" in signing,
        "new feed signer uses versioned random key material and rollback detection",
    ))
    protected_names = ("security_control_plane", "antivirus_policy", "antivirus_suppressions", "antivirus_feed_signing_keys", "cure_firewall_policy", "recovery_policy")
    findings.append(SecurityControlFinding(
        "security_controls_inside_correction_plane",
        "src/zero_os/protected_correction_plane.py",
        "critical",
        all(name in correction for name in protected_names),
        "security authority surfaces are protected correction-plane targets",
    ))

    unresolved = [item for item in findings if not item.resolved]
    critical = [item for item in unresolved if item.severity == "critical"]
    return {
        "status": "PROVISIONAL_SECURITY_CONTROL_PLANE_IN_IDENTIFIED_STATIC_SCOPE" if not critical else "BLOCK_PROMOTION",
        "promotion_permitted": not critical,
        "finding_count": len(findings),
        "unresolved_count": len(unresolved),
        "critical_unresolved_count": len(critical),
        "findings": [item.to_dict() for item in findings],
        "limitations": [
            "legacy_antivirus_call_sites_must_be_migrated_before_promotion",
            "software_key_storage_not_hardware_backed",
            "same_privilege_hostile_code_not_certified",
            "runtime_trace_and_ci_execution_required",
        ],
    }
