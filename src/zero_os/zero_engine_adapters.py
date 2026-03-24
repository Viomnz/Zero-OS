from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from zero_os.antivirus import monitor_status
from zero_os.antivirus_agent import antivirus_agent_status, run_antivirus_agent
from zero_os.cure_firewall_agent import cure_firewall_agent_status, run_cure_firewall_agent
from zero_os.recovery import zero_ai_backup_create, zero_ai_backup_status, zero_ai_recovery_inventory
from zero_os.resilience import (
    external_outage_failover_apply,
    external_outage_status,
    firmware_rootkit_scan,
    immutable_trust_backup_create,
    immutable_trust_backup_status,
    kernel_driver_compromise_status,
)
from zero_os.runtime_smart_logic import recovery_decision, rollout_decision
from zero_os.self_derivation_engine import self_derivation_revalidate, self_derivation_status
from zero_os.zero_ai_pressure_harness import pressure_harness_run, pressure_harness_status


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


def _scan_antivirus(cwd: str, scan_snapshot: dict[str, Any] | None = None) -> dict[str, Any]:
    monitor = monitor_status(cwd)
    report = antivirus_agent_status(cwd)
    return {
        "missing": bool(report.get("missing", False)),
        "finding_count": int(report.get("finding_count", 0) or 0),
        "highest_severity": str(report.get("highest_severity", "low") or "low"),
        "last_change_count": int(monitor.get("last_change_count", 0) or 0),
        "monitor_enabled": bool(monitor.get("enabled", False)),
        "preferred_target": str((scan_snapshot or {}).get("preferred_antivirus_target", ".") or "."),
        "scan_snapshot_changed_path_count": int((scan_snapshot or {}).get("changed_path_count", 0) or 0),
        "report": report,
        "monitor": monitor,
    }


def _scan_firewall(cwd: str, scan_snapshot: dict[str, Any] | None = None) -> dict[str, Any]:
    report = cure_firewall_agent_status(cwd)
    preferred_targets = list((scan_snapshot or {}).get("preferred_firewall_targets") or [])
    return {
        "missing": bool(report.get("missing", False)),
        "system_score": float(report.get("system_score", 0.0) or 0.0),
        "perfect": bool(report.get("perfect", False)),
        "file_targets": int(report.get("file_targets", len(preferred_targets)) or len(preferred_targets)),
        "preferred_file_targets": preferred_targets,
        "report": report,
    }


def _scan_recovery(cwd: str, scan_snapshot: dict[str, Any] | None = None) -> dict[str, Any]:
    status = zero_ai_backup_status(cwd)
    inventory = zero_ai_recovery_inventory(cwd)
    return {
        "snapshot_count": int(status.get("snapshot_count", 0) or 0),
        "latest_snapshot": str(status.get("latest_snapshot", "") or ""),
        "compatible_count": int(inventory.get("compatible_count", 0) or 0),
        "latest_compatible_snapshot_id": str(inventory.get("latest_compatible_snapshot_id", "") or ""),
        "status": status,
        "inventory": inventory,
    }


def _scan_resilience(cwd: str, scan_snapshot: dict[str, Any] | None = None) -> dict[str, Any]:
    kernel = kernel_driver_compromise_status(cwd)
    firmware = firmware_rootkit_scan(cwd)
    outage = external_outage_status(cwd)
    immutable = immutable_trust_backup_status(cwd)
    return {
        "kernel_compromise_signal": bool(kernel.get("compromise_signal", False)),
        "firmware_rootkit_signal": bool(firmware.get("firmware_rootkit_signal", False)),
        "outage_count": int(outage.get("outage_count", 0) or 0),
        "immutable_backup_count": int(immutable.get("count", 0) or 0),
        "kernel": kernel,
        "firmware": firmware,
        "outage": outage,
        "immutable": immutable,
    }


def _scan_pressure(cwd: str, scan_snapshot: dict[str, Any] | None = None) -> dict[str, Any]:
    report = pressure_harness_status(cwd)
    return {
        "missing": bool(report.get("missing", False)),
        "overall_score": float(report.get("overall_score", 0.0) or 0.0),
        "failed_count": int(report.get("failed_count", 0) or 0),
        "scenario_count": int(report.get("scenario_count", 0) or 0),
        "top_failure_code": str(report.get("top_failure_code", "") or ""),
        "report": report,
    }


def _scan_self_derivation(cwd: str, scan_snapshot: dict[str, Any] | None = None) -> dict[str, Any]:
    report = self_derivation_status(cwd)
    return {
        "revalidation_ready_count": int(report.get("revalidation_ready_count", 0) or 0),
        "quarantined_strategy_count": int(report.get("quarantined_strategy_count", 0) or 0),
        "strategy_freshness_score": float(report.get("strategy_freshness_score", 0.0) or 0.0),
        "version_mismatch_count": int(report.get("version_mismatch_count", 0) or 0),
        "top_recovery_profile": str(report.get("top_recovery_profile", "neutral") or "neutral"),
        "report": report,
    }


def _enforce_antivirus(cwd: str, decision: dict[str, Any], facts: dict[str, Any]) -> dict[str, Any]:
    action = str(decision.get("action", "observe"))
    if action == "verify":
        scan_snapshot = dict(facts.get("scan_snapshot") or {})
        target = str(scan_snapshot.get("preferred_antivirus_target", "") or facts.get("preferred_target", "") or ".")
        return run_antivirus_agent(cwd, target=target, auto_quarantine=False, scan_snapshot=scan_snapshot or None)
    return {"ok": True, "action": action, "reason": str(decision.get("reason", "")), "finding_count": int(facts.get("finding_count", 0) or 0)}


def _enforce_firewall(cwd: str, decision: dict[str, Any], facts: dict[str, Any]) -> dict[str, Any]:
    action = str(decision.get("action", "observe"))
    if action == "verify":
        scan_snapshot = dict(facts.get("scan_snapshot") or {})
        targets = list(facts.get("preferred_file_targets") or scan_snapshot.get("preferred_firewall_targets") or [])
        return run_cure_firewall_agent(cwd, pressure=80, targets=targets, verify=True, scan_snapshot=scan_snapshot or None)
    return {"ok": True, "action": action, "reason": str(decision.get("reason", "")), "system_score": float(facts.get("system_score", 0.0) or 0.0)}


def _enforce_recovery(cwd: str, decision: dict[str, Any], facts: dict[str, Any]) -> dict[str, Any]:
    action = str(decision.get("action", "observe"))
    if action == "backup":
        return zero_ai_backup_create(cwd)
    return {"ok": True, "action": action, "reason": str(decision.get("reason", "")), "compatible_count": int(facts.get("compatible_count", 0) or 0)}


def _enforce_resilience(cwd: str, decision: dict[str, Any], facts: dict[str, Any]) -> dict[str, Any]:
    action = str(decision.get("action", "observe"))
    if action == "backup":
        return immutable_trust_backup_create(cwd)
    if action == "failover_apply":
        return external_outage_failover_apply(cwd)
    return {"ok": True, "action": action, "reason": str(decision.get("reason", "")), "outage_count": int(facts.get("outage_count", 0) or 0)}


def _enforce_pressure(cwd: str, decision: dict[str, Any], facts: dict[str, Any]) -> dict[str, Any]:
    action = str(decision.get("action", "observe"))
    if action == "verify":
        return pressure_harness_run(cwd)
    return {
        "ok": True,
        "action": action,
        "reason": str(decision.get("reason", "")),
        "overall_score": float(facts.get("overall_score", 0.0) or 0.0),
    }


def _enforce_self_derivation(cwd: str, decision: dict[str, Any], facts: dict[str, Any]) -> dict[str, Any]:
    action = str(decision.get("action", "observe"))
    if action == "revalidate":
        limit = min(3, max(1, int(facts.get("revalidation_ready_count", 0) or 1)))
        return self_derivation_revalidate(cwd, limit=limit)
    return {
        "ok": True,
        "action": action,
        "reason": str(decision.get("reason", "")),
        "revalidation_ready_count": int(facts.get("revalidation_ready_count", 0) or 0),
    }


def _decide_antivirus(cwd: str, facts: dict[str, Any], *, runtime_context: dict[str, Any] | None = None) -> dict[str, Any]:
    runtime_context = dict(runtime_context or {})
    if not bool(runtime_context.get("continuity_ready", True)):
        return _decision("observe", "continuity_not_ready", confidence=0.45, smart_logic={"engine": "zero_engine_decision_v2"})

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
            smart_logic={"engine": "zero_engine_decision_v2", "highest_severity": highest_severity},
            blockers=["antivirus_findings_present"],
        )
    if missing or change_count > 0:
        return _decision(
            "verify",
            "antivirus_refresh_needed",
            confidence=0.72,
            risk_level="medium" if change_count > 0 else "low",
            smart_logic={"engine": "zero_engine_decision_v2", "last_change_count": change_count},
        )
    return _decision("observe", "antivirus_clean", confidence=0.84, smart_logic={"engine": "zero_engine_decision_v2"})


def _decide_firewall(cwd: str, facts: dict[str, Any], *, runtime_context: dict[str, Any] | None = None) -> dict[str, Any]:
    runtime_context = dict(runtime_context or {})
    if not bool(runtime_context.get("continuity_ready", True)):
        return _decision("observe", "continuity_not_ready", confidence=0.45, smart_logic={"engine": "zero_engine_decision_v2"})

    missing = bool(facts.get("missing", False))
    perfect = bool(facts.get("perfect", False))
    system_score = float(facts.get("system_score", 0.0) or 0.0)
    if missing or not perfect or system_score < 100.0:
        return _decision(
            "verify",
            "firewall_verification_needed",
            confidence=0.76,
            risk_level="medium",
            smart_logic={"engine": "zero_engine_decision_v2", "system_score": system_score},
        )
    return _decision("observe", "firewall_stable", confidence=0.83, smart_logic={"engine": "zero_engine_decision_v2"})


def _decide_recovery(cwd: str, facts: dict[str, Any], *, runtime_context: dict[str, Any] | None = None) -> dict[str, Any]:
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


def _decide_resilience(cwd: str, facts: dict[str, Any], *, runtime_context: dict[str, Any] | None = None) -> dict[str, Any]:
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


def _decide_pressure(cwd: str, facts: dict[str, Any], *, runtime_context: dict[str, Any] | None = None) -> dict[str, Any]:
    missing = bool(facts.get("missing", False))
    overall_score = float(facts.get("overall_score", 0.0) or 0.0)
    failed_count = int(facts.get("failed_count", 0) or 0)
    if missing:
        return _decision(
            "verify",
            "pressure_baseline_missing",
            confidence=0.79,
            risk_level="low",
            smart_logic={"engine": "zero_engine_decision_v2", "overall_score": overall_score},
        )
    if overall_score < 100.0 or failed_count > 0:
        return _decision(
            "verify",
            "pressure_evidence_degraded",
            confidence=0.74,
            risk_level="medium",
            smart_logic={"engine": "zero_engine_decision_v2", "overall_score": overall_score, "failed_count": failed_count},
        )
    return _decision("observe", "pressure_stable", confidence=0.86, smart_logic={"engine": "zero_engine_decision_v2"})


def _decide_self_derivation(cwd: str, facts: dict[str, Any], *, runtime_context: dict[str, Any] | None = None) -> dict[str, Any]:
    runtime_context = dict(runtime_context or {})
    ready_count = int(facts.get("revalidation_ready_count", 0) or 0)
    freshness_score = float(facts.get("strategy_freshness_score", 0.0) or 0.0)
    version_mismatch_count = int(facts.get("version_mismatch_count", 0) or 0)
    pressure_ready = bool(runtime_context.get("pressure_ready", False))
    continuity_ready = bool(runtime_context.get("continuity_ready", True))
    if ready_count > 0 and pressure_ready and continuity_ready:
        return _decision(
            "revalidate",
            "strategy_revalidation_ready",
            confidence=0.77,
            risk_level="low",
            smart_logic={
                "engine": "zero_engine_decision_v2",
                "revalidation_ready_count": ready_count,
                "strategy_freshness_score": freshness_score,
            },
        )
    if ready_count > 0 and (not pressure_ready or not continuity_ready):
        blockers: list[str] = []
        if not pressure_ready:
            blockers.append("pressure_not_ready")
        if not continuity_ready:
            blockers.append("continuity_not_ready")
        return _decision(
            "observe",
            "strategy_revalidation_waiting_on_runtime_conditions",
            confidence=0.59,
            risk_level="low",
            smart_logic={"engine": "zero_engine_decision_v2", "revalidation_ready_count": ready_count},
            blockers=blockers,
        )
    if version_mismatch_count > 0 and freshness_score < 0.5:
        return _decision(
            "observe",
            "strategy_memory_stale",
            confidence=0.66,
            risk_level="low",
            smart_logic={"engine": "zero_engine_decision_v2", "version_mismatch_count": version_mismatch_count},
        )
    return _decision("observe", "self_derivation_stable", confidence=0.82, smart_logic={"engine": "zero_engine_decision_v2"})


@dataclass(frozen=True)
class ZeroEngineAdapter:
    name: str
    interval_seconds: int
    scan: Callable[[str, dict[str, Any] | None], dict[str, Any]]
    decide: Callable[[str, dict[str, Any]], dict[str, Any]]
    enforce: Callable[[str, dict[str, Any], dict[str, Any]], dict[str, Any]]


_ADAPTERS: dict[str, ZeroEngineAdapter] = {}


def register_zero_engine_adapter(adapter: ZeroEngineAdapter, *, replace: bool = False) -> ZeroEngineAdapter:
    if adapter.name in _ADAPTERS and not replace:
        raise ValueError(f"zero engine adapter already registered: {adapter.name}")
    _ADAPTERS[adapter.name] = adapter
    return adapter


def zero_engine_adapters() -> tuple[ZeroEngineAdapter, ...]:
    return tuple(_ADAPTERS[name] for name in sorted(_ADAPTERS))


def zero_engine_adapter_map() -> dict[str, ZeroEngineAdapter]:
    return dict(_ADAPTERS)


def unregister_zero_engine_adapter(name: str) -> ZeroEngineAdapter | None:
    return _ADAPTERS.pop(str(name), None)


def _install_builtin_adapters() -> None:
    if _ADAPTERS:
        return
    register_zero_engine_adapter(
        ZeroEngineAdapter(
            name="antivirus",
            interval_seconds=300,
            scan=_scan_antivirus,
            decide=_decide_antivirus,
            enforce=_enforce_antivirus,
        )
    )
    register_zero_engine_adapter(
        ZeroEngineAdapter(
            name="firewall",
            interval_seconds=300,
            scan=_scan_firewall,
            decide=_decide_firewall,
            enforce=_enforce_firewall,
        )
    )
    register_zero_engine_adapter(
        ZeroEngineAdapter(
            name="recovery",
            interval_seconds=600,
            scan=_scan_recovery,
            decide=_decide_recovery,
            enforce=_enforce_recovery,
        )
    )
    register_zero_engine_adapter(
        ZeroEngineAdapter(
            name="resilience",
            interval_seconds=600,
            scan=_scan_resilience,
            decide=_decide_resilience,
            enforce=_enforce_resilience,
        )
    )
    register_zero_engine_adapter(
        ZeroEngineAdapter(
            name="pressure",
            interval_seconds=900,
            scan=_scan_pressure,
            decide=_decide_pressure,
            enforce=_enforce_pressure,
        )
    )
    register_zero_engine_adapter(
        ZeroEngineAdapter(
            name="self_derivation",
            interval_seconds=900,
            scan=_scan_self_derivation,
            decide=_decide_self_derivation,
            enforce=_enforce_self_derivation,
        )
    )


_install_builtin_adapters()
