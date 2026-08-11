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
    facade = _source(base / "src/zero_os/pure_logic_security_api.py")
    commands = _source(base / "src/zero_os/system_zero_ai_knowledge_security_commands.py")
    agent = _source(base / "src/zero_os/antivirus_agent.py")
    self_repair = _source(base / "src/zero_os/self_repair.py")
    control = _source(base / "src/zero_os/security_control_plane.py")
    signing = _source(base / "src/zero_os/security_signing.py")
    correction = _source(base / "src/zero_os/protected_correction_plane.py")
    findings: list[SecurityControlFinding] = []

    findings.append(SecurityControlFinding(
        "public_security_commands_use_control_plane_facade",
        "src/zero_os/system_zero_ai_knowledge_security_commands.py",
        "critical",
        "from zero_os.pure_logic_security_api import" in commands and "from zero_os.antivirus import (" not in commands,
        "supported security command mutations must enter through the Pure Logic security facade",
    ))
    findings.append(SecurityControlFinding(
        "antivirus_agent_uses_control_plane_facade",
        "src/zero_os/antivirus_agent.py",
        "critical",
        "from zero_os.pure_logic_security_api import quarantine_file, scan_target" in agent,
        "autonomous antivirus agent must consume projected control-plane state",
    ))
    findings.append(SecurityControlFinding(
        "self_repair_does_not_expand_security_policy",
        "src/zero_os/self_repair.py",
        "critical",
        "monitor_set" not in self_repair and "policy_change:enable_antivirus_monitor" in self_repair,
        "self-repair authority may request but may not silently grant security-policy authority",
    ))
    findings.append(SecurityControlFinding(
        "security_facade_projects_control_plane_state",
        "src/zero_os/pure_logic_security_api.py",
        "critical",
        all(token in facade for token in ("load_state", "mutate_state", "reconcile_security_projection", "sign_antivirus_feed", "verify_antivirus_feed")),
        "legacy scanner state must be a projection of protected control-plane state on supported paths",
    ))

    deterministic_feed_key = "hashlib.sha256(str(key_path).encode" in antivirus
    findings.append(SecurityControlFinding(
        "legacy_antivirus_deterministic_feed_key_removed",
        "src/zero_os/antivirus.py",
        "critical",
        not deterministic_feed_key,
        "legacy signer remains a direct-call trust risk until removed or mechanically disabled",
    ))

    legacy_policy_mutators = all(name in antivirus for name in ("def policy_set", "def suppression_add", "def suppression_remove"))
    legacy_has_authority_handoff = "acknowledge_consumed_execution_ticket" in antivirus or "mutate_state(" in antivirus or "mutate_batch(" in antivirus
    findings.append(SecurityControlFinding(
        "legacy_antivirus_control_mutators_removed_or_mediated",
        "src/zero_os/antivirus.py",
        "critical",
        (not legacy_policy_mutators) or legacy_has_authority_handoff,
        "direct import of legacy policy/suppression mutation remains a bypass until removed or mediated",
    ))

    findings.append(SecurityControlFinding(
        "security_control_plane_requires_runtime_handoff",
        "src/zero_os/security_control_plane.py",
        "critical",
        "acknowledge_consumed_execution_ticket" in control and "policy_change" in control,
        "control-plane mutation consumes constitution-authorized policy_change handoff",
    ))
    findings.append(SecurityControlFinding(
        "security_control_plane_validates_before_authority_consumption",
        "src/zero_os/security_control_plane.py",
        "critical",
        control.find("_plan_mutations(current, normalized)") >= 0 and control.find("_plan_mutations(current, normalized)") < control.find("handoff = _authorized_security_change(cwd)"),
        "malformed operations must not consume a valid single-use authority ticket",
    ))
    findings.append(SecurityControlFinding(
        "security_control_history_is_link_verified",
        "src/zero_os/security_control_plane.py",
        "high",
        all(token in control for token in ("security_control_history_chain_mismatch", "security_control_head_digest_mismatch", "previous_digest")),
        "history verification checks revision/digest linkage rather than record count only",
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
        "resolved_count": len(findings) - len(unresolved),
        "unresolved_count": len(unresolved),
        "critical_unresolved_count": len(critical),
        "findings": [item.to_dict() for item in findings],
        "limitations": [
            "legacy_antivirus_direct_import_surface_remains_until engine authority functions are removed",
            "software_key_storage_not_hardware_backed",
            "same_privilege_hostile_code_not_certified",
            "native_and_non_python_paths_not_certified",
            "runtime_trace_and_ci_execution_required",
        ],
    }
