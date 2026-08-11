from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SinkAuditResult:
    passed: bool
    status: str
    reasons: tuple[str, ...]
    checked_files: tuple[str, ...]


def audit_sink_enforcement(root: str | Path) -> SinkAuditResult:
    base = Path(root)
    requirements = {
        "src/zero_os/protected_data_runtime.py": (
            "evaluate_sensitive_sink",
            "expected_containment_revision",
            "containment_revision",
            "sensitive_plaintext_read_requires_isolated_broker",
        ),
        "src/zero_os/protected_data_broker_runtime.py": (
            "evaluate_sensitive_sink",
            "containment_enforced_by_broker",
            "broker_containment_revision_mismatch",
        ),
        "src/zero_os/protected_export_sinks.py": (
            "ExportAuthorizationEvidence",
            "evaluate_sensitive_sink",
            "actuator(",
            "authority_granted: bool = False",
            "protected_export_destination_binding_mismatch",
            "protected_export_process_binding_mismatch",
        ),
        "src/zero_os/containment_sink_enforcement.py": (
            "live_containment_state_missing",
            "process_identity_not_kernel_bound",
            "containment_revision_stale",
            "path_logic_final_authority: bool = False",
        ),
        "src/zero_os/live_containment_state.py": (
            "register_kernel_evidence",
            "plain_string_registration_fails_closed",
            "identity_verification_cannot_clear_contradictions",
        ),
        "src/zero_os/process_identity_evidence.py": (
            "process_lifetime_binding_required",
            "caller_label_cannot_establish_process_identity",
            "production_requires_real_kernel_source",
        ),
    }
    forbidden = {
        "src/zero_os/protected_export_sinks.py": (
            "authorization_verified: bool",
            "if not authorization_verified",
        ),
        "src/zero_os/decoy_event_ingest.py": (
            "event.actor_id in set(beacon.expected_accessors)",
        ),
        "src/zero_os/decoy_beacon.py": (
            "touch.actor_id in set(beacon.expected_accessors)",
        ),
    }
    reasons: list[str] = []
    checked: list[str] = []
    texts: dict[str, str] = {}
    for relative, markers in requirements.items():
        path = base / relative
        checked.append(relative)
        if not path.exists():
            reasons.append(f"missing:{relative}")
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        texts[relative] = text
        for marker in markers:
            if marker not in text:
                reasons.append(f"missing_marker:{relative}:{marker}")

    for relative, markers in forbidden.items():
        path = base / relative
        text = texts.get(relative)
        if text is None and path.exists():
            text = path.read_text(encoding="utf-8", errors="replace")
            texts[relative] = text
        for marker in markers:
            if marker in (text or ""):
                reasons.append(f"forbidden_legacy_pattern:{relative}:{marker}")

    # A sink must never import path ranking as an authority source.
    for relative, text in texts.items():
        lowered = text.lower()
        if "from zero_os.path" in lowered and "authority" in lowered:
            reasons.append(f"path_logic_authority_dependency:{relative}")

    return SinkAuditResult(
        passed=not reasons,
        status="SINK_ENFORCEMENT_STATIC_AUDIT_PASS" if not reasons else "SINK_ENFORCEMENT_STATIC_AUDIT_FAIL",
        reasons=tuple(reasons),
        checked_files=tuple(checked),
    )
