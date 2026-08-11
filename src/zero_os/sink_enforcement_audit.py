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
        ),
        "src/zero_os/protected_data_broker_runtime.py": (
            "evaluate_sensitive_sink",
            "containment_enforced_by_broker",
            "broker_containment_revision_mismatch",
        ),
        "src/zero_os/protected_export_sinks.py": (
            "evaluate_sensitive_sink",
            "actuator(",
            "authority_granted: bool = False",
        ),
        "src/zero_os/containment_sink_enforcement.py": (
            "live_containment_state_missing",
            "containment_revision_stale",
            "path_logic_final_authority: bool = False",
        ),
    }
    reasons: list[str] = []
    checked: list[str] = []
    for relative, markers in requirements.items():
        path = base / relative
        checked.append(relative)
        if not path.exists():
            reasons.append(f"missing:{relative}")
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for marker in markers:
            if marker not in text:
                reasons.append(f"missing_marker:{relative}:{marker}")

    # A sink must never import path ranking as an authority source.
    for relative in checked:
        path = base / relative
        if path.exists():
            text = path.read_text(encoding="utf-8", errors="replace").lower()
            if "from zero_os.path" in text and "authority" in text:
                reasons.append(f"path_logic_authority_dependency:{relative}")

    return SinkAuditResult(
        passed=not reasons,
        status="SINK_ENFORCEMENT_STATIC_AUDIT_PASS" if not reasons else "SINK_ENFORCEMENT_STATIC_AUDIT_FAIL",
        reasons=tuple(reasons),
        checked_files=tuple(checked),
    )
