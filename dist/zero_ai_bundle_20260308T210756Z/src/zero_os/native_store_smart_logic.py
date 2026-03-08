from __future__ import annotations

from zero_os.smart_logic_governance import apply_governance


def _root_issues(issue_sources: list[str], failed_checks: list[str] | None = None) -> dict:
    return {"issue_sources": issue_sources, "failed_checks": failed_checks or []}


def package_decision(cwd: str, operation: str, target_os: str, available: bool, signed: bool, trusted: bool) -> dict:
    confidence = 0.45
    issues: list[str] = []
    failed: list[str] = []
    action = "allow_with_monitoring"
    reason = "package_checks_pass"
    if available:
        confidence += 0.2
    else:
        issues.append("artifact_missing")
        failed.append("artifact_available")
    if signed:
        confidence += 0.2
    else:
        issues.append("unsigned_artifact")
        failed.append("artifact_signed")
    if trusted:
        confidence += 0.15
    else:
        issues.append("trust_not_established")
        failed.append("artifact_trusted")
    if not available:
        action = "reject_or_hold"
        reason = "artifact_unavailable"
    elif not signed or not trusted:
        action = "hold_for_review"
        reason = "package_risk_requires_review"
    logic = {
        "engine": "native_store_package_smart_logic_v1",
        "decision_action": action,
        "decision_reason": reason,
        "confidence": round(max(0.0, min(0.99, confidence)), 4),
        "root_issues": _root_issues(issues, failed),
        "operation": operation,
        "target_os": target_os,
    }
    return apply_governance(cwd, logic, {"operation": operation, "target_os": target_os})


def rollback_decision(cwd: str, checkpoint_exists: bool, risk_level: str) -> dict:
    confidence = 0.72 if checkpoint_exists else 0.25
    issues: list[str] = []
    failed: list[str] = []
    action = "allow"
    reason = "rollback_ready"
    if not checkpoint_exists:
        issues.append("checkpoint_missing")
        failed.append("checkpoint_exists")
        action = "reject_or_hold"
        reason = "rollback_checkpoint_missing"
    if risk_level.lower() in {"high", "critical"}:
        confidence -= 0.08
        issues.append("high_risk_environment")
    logic = {
        "engine": "native_store_rollback_smart_logic_v1",
        "decision_action": action,
        "decision_reason": reason,
        "confidence": round(max(0.0, min(0.99, confidence)), 4),
        "root_issues": _root_issues(issues, failed),
    }
    return apply_governance(cwd, logic, {"risk_level": risk_level.lower()})


def release_gate_decision(cwd: str, stress_ok: bool, signed: bool, incidents_open: int) -> dict:
    confidence = 0.4
    issues: list[str] = []
    failed: list[str] = []
    action = "allow"
    reason = "release_gate_pass"
    if stress_ok:
        confidence += 0.25
    else:
        issues.append("stress_gate_failed")
        failed.append("stress_ok")
    if signed:
        confidence += 0.25
    else:
        issues.append("unsigned_release")
        failed.append("signed")
    if incidents_open == 0:
        confidence += 0.1
    else:
        issues.append("open_incidents")
        failed.append("incidents_clear")
    if not stress_ok or not signed or incidents_open > 0:
        action = "hold_for_review"
        reason = "release_gate_requires_review"
    logic = {
        "engine": "native_store_release_smart_logic_v1",
        "decision_action": action,
        "decision_reason": reason,
        "confidence": round(max(0.0, min(0.99, confidence)), 4),
        "root_issues": _root_issues(issues, failed),
    }
    return apply_governance(cwd, logic, {"incidents_open": incidents_open})


def incident_decision(cwd: str, severity: str, blast_radius: str) -> dict:
    sev = severity.lower()
    radius = blast_radius.lower()
    confidence = 0.75 if sev in {"sev1", "sev2", "critical", "high"} else 0.6
    action = "manual_containment" if radius in {"global", "multi-region"} or sev in {"sev1", "critical"} else "allow_with_monitoring"
    reason = "incident_response_required" if action == "manual_containment" else "incident_monitoring"
    issues = ["broad_blast_radius"] if radius in {"global", "multi-region"} else []
    logic = {
        "engine": "native_store_incident_smart_logic_v1",
        "decision_action": action,
        "decision_reason": reason,
        "confidence": confidence,
        "root_issues": _root_issues(issues, []),
    }
    return apply_governance(cwd, logic, {"severity": sev, "blast_radius": radius})


def abuse_decision(cwd: str, abuse_score: float, repeat_offender: bool) -> dict:
    score = float(abuse_score)
    action = "allow_with_monitoring"
    reason = "abuse_below_threshold"
    issues: list[str] = []
    failed: list[str] = []
    confidence = min(0.99, 0.45 + score / 100.0)
    if score >= 70 or repeat_offender:
        action = "block"
        reason = "abuse_threshold_exceeded"
        issues.append("abuse_threshold_exceeded")
        failed.append("abuse_below_threshold")
    logic = {
        "engine": "native_store_abuse_smart_logic_v1",
        "decision_action": action,
        "decision_reason": reason,
        "confidence": confidence,
        "root_issues": _root_issues(issues, failed),
    }
    return apply_governance(cwd, logic, {"abuse_score": score, "repeat_offender": repeat_offender})


def trust_decision(cwd: str, signed: bool, cert_active: bool, secret_platform: bool) -> dict:
    confidence = 0.35
    issues: list[str] = []
    failed: list[str] = []
    action = "allow"
    reason = "trust_chain_ready"
    for ok, issue, check, weight in (
        (signed, "unsigned_artifact", "signed", 0.25),
        (cert_active, "inactive_certificate", "certificate_active", 0.2),
        (secret_platform, "secret_platform_unavailable", "secret_platform", 0.2),
    ):
        if ok:
            confidence += weight
        else:
            issues.append(issue)
            failed.append(check)
    if issues:
        action = "hold_for_review"
        reason = "trust_chain_incomplete"
    logic = {
        "engine": "native_store_trust_smart_logic_v1",
        "decision_action": action,
        "decision_reason": reason,
        "confidence": round(max(0.0, min(0.99, confidence)), 4),
        "root_issues": _root_issues(issues, failed),
    }
    return apply_governance(cwd, logic, {})
