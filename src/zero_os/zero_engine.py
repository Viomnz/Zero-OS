from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any

from zero_os.antivirus import monitor_status
from zero_os.antivirus_agent import antivirus_agent_status, run_antivirus_agent
from zero_os.cure_firewall_agent import cure_firewall_agent_status, run_cure_firewall_agent
from zero_os.decision_engine import decide_zero_engine
from zero_os.recovery import zero_ai_backup_create, zero_ai_backup_status, zero_ai_recovery_inventory
from zero_os.resilience import (
    external_outage_failover_apply,
    external_outage_status,
    firmware_rootkit_scan,
    immutable_trust_backup_create,
    immutable_trust_backup_status,
    kernel_driver_compromise_status,
)
from zero_os.scan_coordinator import build_workspace_scan_snapshot, workspace_scan_summary
from zero_os.state_registry import boot_state_registry, flush_state_registry, get_state_store, put_state_store


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _engine_path(cwd: str) -> Path:
    return Path(cwd).resolve() / ".zero_os" / "runtime" / "zero_engine_status.json"


def _default_state() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "last_run_utc": "",
        "subsystems": {
            "antivirus": {"interval_seconds": 300, "last_run_utc": "", "last_decision": {}, "last_result": {}},
            "firewall": {"interval_seconds": 300, "last_run_utc": "", "last_decision": {}, "last_result": {}},
            "recovery": {"interval_seconds": 600, "last_run_utc": "", "last_decision": {}, "last_result": {}},
            "resilience": {"interval_seconds": 600, "last_run_utc": "", "last_decision": {}, "last_result": {}},
        },
        "latest_report": {},
    }


def _parse_utc(value: str) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _due(last_run_utc: str, interval_seconds: int, *, force: bool = False) -> bool:
    if force:
        return True
    last_run = _parse_utc(last_run_utc)
    if last_run is None:
        return True
    return (datetime.now(timezone.utc) - last_run).total_seconds() >= max(30, int(interval_seconds or 60))


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


_SCAN_HANDLERS = {
    "antivirus": _scan_antivirus,
    "firewall": _scan_firewall,
    "recovery": _scan_recovery,
    "resilience": _scan_resilience,
}

_ENFORCE_HANDLERS = {
    "antivirus": _enforce_antivirus,
    "firewall": _enforce_firewall,
    "recovery": _enforce_recovery,
    "resilience": _enforce_resilience,
}


def zero_engine_status(cwd: str) -> dict[str, Any]:
    boot_state_registry(cwd)
    state = get_state_store(cwd, "zero_engine_status", _default_state())
    if not state:
        state = _default_state()
    state.setdefault("schema_version", 1)
    state.setdefault("subsystems", deepcopy(_default_state()["subsystems"]))
    return {
        "ok": True,
        "path": str(_engine_path(cwd)),
        **state,
    }


def zero_engine_tick(cwd: str, *, force: bool = False, runtime_context: dict[str, Any] | None = None) -> dict[str, Any]:
    boot_state_registry(cwd)
    state = get_state_store(cwd, "zero_engine_status", _default_state())
    if not state:
        state = _default_state()
    subsystems = dict(state.get("subsystems") or {})
    for name, default_state in _default_state()["subsystems"].items():
        current = dict(subsystems.get(name) or {})
        for key, value in default_state.items():
            current.setdefault(key, value)
        subsystems[name] = current

    scan_started = perf_counter()
    scan_snapshot = build_workspace_scan_snapshot(cwd, force=force)
    scan_summary = workspace_scan_summary(scan_snapshot)
    facts: dict[str, Any] = {}
    scan_errors: dict[str, Any] = {}
    with ThreadPoolExecutor(max_workers=max(1, len(_SCAN_HANDLERS))) as executor:
        futures = {
            executor.submit(_SCAN_HANDLERS[name], cwd, scan_snapshot): name
            for name in _SCAN_HANDLERS
        }
        for future in as_completed(futures):
            name = futures[future]
            try:
                subsystem_facts = dict(future.result() or {})
            except Exception as exc:
                subsystem_facts = {
                    "missing": True,
                    "scan_error": str(exc),
                    "report": {"ok": False, "reason": str(exc)},
                }
                scan_errors[name] = {"reason": str(exc)}
            subsystem_facts["scan_snapshot"] = scan_snapshot
            facts[name] = subsystem_facts
    scan_duration_ms = round((perf_counter() - scan_started) * 1000.0, 3)
    decision_block = decide_zero_engine(cwd, facts, runtime_context=runtime_context)
    decisions = dict(decision_block.get("decisions") or {})
    subsystem_reports: dict[str, Any] = {}
    ran_count = 0
    now_utc = _utc_now()

    for name, subsystem_state in subsystems.items():
        decision = dict(decisions.get(name) or {})
        interval_seconds = int(subsystem_state.get("interval_seconds", 300) or 300)
        fact_report = dict(facts.get(name) or {})
        if "scan_snapshot" in fact_report:
            fact_report["scan_snapshot"] = scan_summary
        if not _due(str(subsystem_state.get("last_run_utc", "")), interval_seconds, force=force):
            subsystem_reports[name] = {
                "ok": True,
                "ran": False,
                "reason": "subsystem not due",
                "decision": decision,
                "facts": fact_report,
            }
            continue
        result = _ENFORCE_HANDLERS[name](cwd, decision, dict(facts.get(name) or {}))
        subsystem_state["last_run_utc"] = now_utc
        subsystem_state["last_decision"] = decision
        subsystem_state["last_result"] = result
        subsystem_state["last_reason"] = str(decision.get("reason", ""))
        subsystem_reports[name] = {
            "ok": bool(result.get("ok", False)),
            "ran": True,
            "decision": decision,
            "facts": fact_report,
            "result": result,
        }
        ran_count += 1

    report = {
        "ok": True,
        "generated_utc": now_utc,
        "ran_count": ran_count,
        "subsystem_count": len(subsystems),
        "decisions": decisions,
        "next_priority_subsystem": str(decision_block.get("next_priority_subsystem", "")),
        "next_priority_action": str(decision_block.get("next_priority_action", "")),
        "next_priority_reason": str(decision_block.get("next_priority_reason", "")),
        "scan_mode": "parallel",
        "scan_duration_ms": scan_duration_ms,
        "scan_error_count": len(scan_errors),
        "scan_errors": scan_errors,
        "scan_snapshot": scan_summary,
        "subsystems": subsystem_reports,
    }
    state["schema_version"] = 1
    state["last_run_utc"] = now_utc
    state["subsystems"] = subsystems
    state["latest_report"] = report
    put_state_store(cwd, "zero_engine_status", state)
    flush_state_registry(cwd, names=["zero_engine_status", "workspace_scan_snapshot"])
    return {
        "ok": True,
        "path": str(_engine_path(cwd)),
        **state,
    }
