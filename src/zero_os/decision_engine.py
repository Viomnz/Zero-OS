from __future__ import annotations

from typing import Any

from zero_os.runtime_smart_logic import recovery_decision, rollout_decision


def _decision(
    action: str,
    reason: str,
    *,
    confidence: float,
    risk_level: str = "low",
    requires_approval_possible: bool = False,
    smart_logic: dict[str, Any] | None = None,
    blockers: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "action": str(action),
        "reason": str(reason),
        "confidence": round(max(0.0, min(0.99, float(confidence))), 3),
        "risk_level": str(risk_level or "low"),
        "requires_approval_possible": bool(requires_approval_possible),
        "smart_logic": dict(smart_logic or {}),
        "blockers": list(blockers or []),
    }


def decide_maintenance_action(snapshot: dict[str, Any]) -> dict[str, Any]:
    runtime = dict(snapshot.get("runtime") or {})
    flow = dict(snapshot.get("flow") or {})
    pressure = dict(snapshot.get("pressure") or {})
    self_derivation = dict(snapshot.get("self_derivation") or {})
    contradiction = dict(snapshot.get("contradiction") or {})
    workflows = dict(snapshot.get("workflows") or {})
    backups = dict(snapshot.get("backups") or {})

    continuity = dict(contradiction.get("continuity") or {})
    if bool(continuity.get("has_contradiction", False)) or not bool(continuity.get("same_system", True)):
        return {"action": "observe", "reason": "contradiction_hold", "summary": "Maintenance is blocked until self contradiction clears."}

    if bool(runtime.get("missing", False)) or not bool(runtime.get("runtime_ready", False)):
        return {"action": "runtime_run", "reason": "runtime_not_ready", "summary": "Run phase runtime to restore the maintenance control plane."}

    flow_score = float(((flow.get("summary") or {}).get("flow_score", 0.0)) or 0.0)
    self_repair_lane = dict(((workflows.get("lanes") or {}).get("self_repair")) or {})
    if flow_score < 100.0 and bool(self_repair_lane.get("ready", False)) and bool(self_repair_lane.get("active", False)):
        return {"action": "self_repair", "reason": "flow_degraded", "summary": "Run canary-backed self repair to lift flow and health signals."}

    if bool(pressure.get("missing", False)) or float(pressure.get("overall_score", 0.0) or 0.0) < 100.0:
        return {"action": "pressure_run", "reason": "pressure_baseline_missing_or_low", "summary": "Run the pressure harness to refresh survivability evidence."}

    revalidation_ready_count = int(self_derivation.get("revalidation_ready_count", 0) or 0)
    if revalidation_ready_count > 0:
        return {
            "action": "self_derivation_revalidate",
            "reason": "strategy_revalidation_ready",
            "summary": f"Run bounded self-derivation canary revalidation for {revalidation_ready_count} ready quarantined strategies.",
        }

    if int(backups.get("snapshot_count", 0) or 0) == 0:
        return {"action": "observe", "reason": "snapshot_baseline_missing", "summary": "Create a fresh recovery snapshot before trusting broader maintenance automation."}

    return {"action": "observe", "reason": "stable", "summary": "System is stable; continue monitoring instead of mutating."}


def decide_antivirus_action(cwd: str, facts: dict[str, Any], *, runtime_context: dict[str, Any] | None = None) -> dict[str, Any]:
    runtime_context = dict(runtime_context or {})
    if not bool(runtime_context.get("continuity_ready", True)):
        return _decision("observe", "continuity_not_ready", confidence=0.45, smart_logic={"engine": "zero_engine_decision_v1"})

    finding_count = int(facts.get("finding_count", 0) or 0)
    highest_severity = str(facts.get("highest_severity", "low") or "low")
    missing = bool(facts.get("missing", False))
    change_count = int(facts.get("last_change_count", 0) or 0)
    if finding_count > 0:
        return _decision(
            "hold_for_review",
            "antivirus_findings_present",
            confidence=0.91,
            risk_level="high" if highest_severity in {"high", "critical"} else "medium",
            requires_approval_possible=True,
            smart_logic={"engine": "zero_engine_decision_v1", "highest_severity": highest_severity},
            blockers=["antivirus_findings_present"],
        )
    if missing or change_count > 0:
        return _decision(
            "verify",
            "antivirus_refresh_needed",
            confidence=0.72,
            risk_level="medium" if change_count > 0 else "low",
            smart_logic={"engine": "zero_engine_decision_v1", "last_change_count": change_count},
        )
    return _decision("observe", "antivirus_clean", confidence=0.84, smart_logic={"engine": "zero_engine_decision_v1"})


def decide_firewall_action(cwd: str, facts: dict[str, Any], *, runtime_context: dict[str, Any] | None = None) -> dict[str, Any]:
    runtime_context = dict(runtime_context or {})
    if not bool(runtime_context.get("continuity_ready", True)):
        return _decision("observe", "continuity_not_ready", confidence=0.45, smart_logic={"engine": "zero_engine_decision_v1"})

    missing = bool(facts.get("missing", False))
    perfect = bool(facts.get("perfect", False))
    system_score = float(facts.get("system_score", 0.0) or 0.0)
    if missing or not perfect or system_score < 100.0:
        return _decision(
            "verify",
            "firewall_verification_needed",
            confidence=0.76,
            risk_level="medium",
            smart_logic={"engine": "zero_engine_decision_v1", "system_score": system_score},
        )
    return _decision("observe", "firewall_stable", confidence=0.83, smart_logic={"engine": "zero_engine_decision_v1"})


def decide_recovery_action(cwd: str, facts: dict[str, Any], *, runtime_context: dict[str, Any] | None = None) -> dict[str, Any]:
    snapshot_count = int(facts.get("snapshot_count", 0) or 0)
    compatible_count = int(facts.get("compatible_count", 0) or 0)
    logic = recovery_decision(cwd, snapshot_count > 0, compatible_count > 0, "system")
    if snapshot_count <= 0:
        return _decision(
            "backup",
            "recovery_snapshot_missing",
            confidence=float(logic.get("confidence", 0.65) or 0.65),
            risk_level="medium",
            smart_logic=logic,
        )
    if compatible_count <= 0:
        return _decision(
            "hold_for_review",
            "recovery_no_compatible_snapshot",
            confidence=float(logic.get("confidence", 0.58) or 0.58),
            risk_level="high",
            requires_approval_possible=True,
            smart_logic=logic,
            blockers=["latest_compatible_snapshot_missing"],
        )
    return _decision("observe", "recovery_ready", confidence=float(logic.get("confidence", 0.8) or 0.8), smart_logic=logic)


def decide_resilience_action(cwd: str, facts: dict[str, Any], *, runtime_context: dict[str, Any] | None = None) -> dict[str, Any]:
    outage_count = int(facts.get("outage_count", 0) or 0)
    immutable_backup_count = int(facts.get("immutable_backup_count", 0) or 0)
    kernel_compromise_signal = bool(facts.get("kernel_compromise_signal", False))
    firmware_rootkit_signal = bool(facts.get("firmware_rootkit_signal", False))
    logic = rollout_decision(cwd, "prod", True, outage_count)
    if kernel_compromise_signal or firmware_rootkit_signal:
        return _decision(
            "hold_for_review",
            "resilience_host_compromise_signal",
            confidence=0.94,
            risk_level="high",
            requires_approval_possible=True,
            smart_logic=logic,
            blockers=["host_compromise_signal"],
        )
    if outage_count > 0:
        return _decision(
            "failover_apply",
            "external_outage_present",
            confidence=float(logic.get("confidence", 0.8) or 0.8),
            risk_level="medium",
            smart_logic=logic,
        )
    if immutable_backup_count <= 0:
        return _decision(
            "backup",
            "immutable_trust_backup_missing",
            confidence=0.78,
            risk_level="low",
            smart_logic=logic,
        )
    return _decision("observe", "resilience_stable", confidence=float(logic.get("confidence", 0.82) or 0.82), smart_logic=logic)


def decide_zero_engine(cwd: str, facts: dict[str, Any], *, runtime_context: dict[str, Any] | None = None) -> dict[str, Any]:
    runtime_context = dict(runtime_context or {})
    decisions = {
        "antivirus": decide_antivirus_action(cwd, dict(facts.get("antivirus") or {}), runtime_context=runtime_context),
        "firewall": decide_firewall_action(cwd, dict(facts.get("firewall") or {}), runtime_context=runtime_context),
        "recovery": decide_recovery_action(cwd, dict(facts.get("recovery") or {}), runtime_context=runtime_context),
        "resilience": decide_resilience_action(cwd, dict(facts.get("resilience") or {}), runtime_context=runtime_context),
    }
    priority = {
        "hold_for_review": 4,
        "failover_apply": 3,
        "backup": 2,
        "verify": 1,
        "observe": 0,
    }
    next_subsystem = max(
        decisions.items(),
        key=lambda item: (
            priority.get(str(item[1].get("action", "observe")), 0),
            float(item[1].get("confidence", 0.0) or 0.0),
            str(item[0]),
        ),
    )
    return {
        "ok": True,
        "decisions": decisions,
        "next_priority_subsystem": str(next_subsystem[0]),
        "next_priority_action": str(next_subsystem[1].get("action", "observe")),
        "next_priority_reason": str(next_subsystem[1].get("reason", "")),
    }
