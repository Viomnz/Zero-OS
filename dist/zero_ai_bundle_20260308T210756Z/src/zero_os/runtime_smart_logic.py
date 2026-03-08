from __future__ import annotations

from zero_os.smart_logic_governance import apply_governance


def _root_issues(issue_sources: list[str], failed_checks: list[str] | None = None) -> dict:
    return {"issue_sources": issue_sources, "failed_checks": failed_checks or []}


def security_action_decision(cwd: str, trust_ready: bool, strict_mode: bool, antivirus_ready: bool) -> dict:
    confidence = 0.4
    issues: list[str] = []
    failed: list[str] = []
    action = "allow_with_monitoring"
    reason = "security_baseline_ready"
    for ok, issue, check, weight in (
        (trust_ready, "trust_root_missing", "trust_ready", 0.25),
        (strict_mode, "strict_mode_not_enabled", "strict_mode", 0.2),
        (antivirus_ready, "antivirus_not_enabled", "antivirus_ready", 0.2),
    ):
        if ok:
            confidence += weight
        else:
            issues.append(issue)
            failed.append(check)
    if not trust_ready:
        action = "hold_for_review"
        reason = "security_trust_chain_incomplete"
    logic = {
        "engine": "zero_os_security_action_smart_logic_v1",
        "decision_action": action,
        "decision_reason": reason,
        "confidence": round(max(0.0, min(0.99, confidence)), 4),
        "root_issues": _root_issues(issues, failed),
    }
    return apply_governance(cwd, logic, {"strict_mode": strict_mode})


def recovery_decision(cwd: str, snapshot_exists: bool, integrity_ok: bool, blast_radius: str) -> dict:
    radius = blast_radius.strip().lower()
    confidence = 0.35
    issues: list[str] = []
    failed: list[str] = []
    action = "allow"
    reason = "recovery_ready"
    if snapshot_exists:
        confidence += 0.3
    else:
        issues.append("snapshot_missing")
        failed.append("snapshot_exists")
    if integrity_ok:
        confidence += 0.22
    else:
        issues.append("integrity_unverified")
        failed.append("integrity_ok")
        action = "hold_for_review"
        reason = "recovery_integrity_uncertain"
    if radius in {"global", "multi-region", "system"}:
        confidence += 0.08
    if not snapshot_exists:
        action = "reject_or_hold"
        reason = "recovery_snapshot_missing"
    logic = {
        "engine": "zero_os_recovery_smart_logic_v1",
        "decision_action": action,
        "decision_reason": reason,
        "confidence": round(max(0.0, min(0.99, confidence)), 4),
        "root_issues": _root_issues(issues, failed),
    }
    return apply_governance(cwd, logic, {"blast_radius": radius})


def rollout_decision(cwd: str, environment: str, signed: bool, outage_count: int) -> dict:
    env = environment.strip().lower()
    confidence = 0.45
    issues: list[str] = []
    failed: list[str] = []
    action = "allow"
    reason = "rollout_ready"
    if env in {"dev", "stage", "prod"}:
        confidence += 0.1
    if signed:
        confidence += 0.2
    else:
        issues.append("unsigned_rollout")
        failed.append("signed")
    if outage_count == 0:
        confidence += 0.15
    else:
        issues.append("integration_outages_present")
        failed.append("outages_clear")
    if env == "prod" and (not signed or outage_count > 0):
        action = "hold_for_review"
        reason = "prod_rollout_requires_review"
    logic = {
        "engine": "zero_os_rollout_smart_logic_v1",
        "decision_action": action,
        "decision_reason": reason,
        "confidence": round(max(0.0, min(0.99, confidence)), 4),
        "root_issues": _root_issues(issues, failed),
    }
    return apply_governance(cwd, logic, {"environment": env, "outage_count": int(outage_count)})


def abuse_throttle_decision(cwd: str, used: int, limit: int, retry_after_seconds: int) -> dict:
    cap = max(1, int(limit))
    consumed = max(0, int(used))
    retry = max(0, int(retry_after_seconds))
    ratio = min(2.0, consumed / cap)
    confidence = min(0.99, 0.4 + ratio * 0.35)
    issues: list[str] = []
    failed: list[str] = []
    action = "allow_with_monitoring"
    reason = "traffic_within_threshold"
    if consumed >= cap:
        action = "block"
        reason = "rate_limit_exceeded"
        issues.append("rate_limit_exceeded")
        failed.append("under_limit")
    elif consumed >= max(1, int(cap * 0.8)):
        action = "hold_for_review"
        reason = "rate_limit_near_capacity"
        issues.append("near_capacity")
    logic = {
        "engine": "zero_os_abuse_throttle_smart_logic_v1",
        "decision_action": action,
        "decision_reason": reason,
        "confidence": round(confidence, 4),
        "root_issues": _root_issues(issues, failed),
    }
    return apply_governance(cwd, logic, {"used": consumed, "limit": cap, "retry_after_seconds": retry})


def permission_trust_decision(cwd: str, role: str, critical: bool, signed: bool, forbidden: bool) -> dict:
    role_n = role.strip().lower()
    confidence = 0.45
    issues: list[str] = []
    failed: list[str] = []
    action = "allow"
    reason = "permission_checks_pass"
    if role_n in {"admin", "operator"}:
        confidence += 0.15
    else:
        issues.append("insufficient_role")
        failed.append("role_permitted")
        action = "block"
        reason = "role_forbidden"
    if critical:
        confidence += 0.1
        if signed:
            confidence += 0.15
        else:
            issues.append("critical_action_unsigned")
            failed.append("critical_action_signed")
            action = "hold_for_review"
            reason = "critical_action_requires_signature"
    if forbidden:
        issues.append("forbidden_prefix")
        failed.append("command_not_forbidden")
        action = "block"
        reason = "forbidden_command"
    logic = {
        "engine": "zero_os_permission_trust_smart_logic_v1",
        "decision_action": action,
        "decision_reason": reason,
        "confidence": round(max(0.0, min(0.99, confidence)), 4),
        "root_issues": _root_issues(issues, failed),
    }
    return apply_governance(cwd, logic, {"role": role_n, "critical": bool(critical), "forbidden": bool(forbidden)})
