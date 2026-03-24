from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any

from zero_os.decision_engine import decide_zero_engine
from zero_os.scan_coordinator import build_workspace_scan_snapshot, workspace_scan_summary
from zero_os.state_registry import (
    boot_state_registry,
    flush_state_registry,
    get_state_store,
    update_state_store,
)
from zero_os.zero_engine_adapters import zero_engine_adapters


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _engine_path(cwd: str) -> Path:
    return Path(cwd).resolve() / ".zero_os" / "runtime" / "zero_engine_status.json"


def _default_subsystems() -> dict[str, Any]:
    return {
        adapter.name: {
            "interval_seconds": int(adapter.interval_seconds),
            "last_run_utc": "",
            "last_decision": {},
            "last_result": {},
        }
        for adapter in zero_engine_adapters()
    }


def _default_state() -> dict[str, Any]:
    return {
        "schema_version": 2,
        "last_run_utc": "",
        "subsystems": _default_subsystems(),
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


def _normalize_state(raw_state: dict[str, Any] | None) -> dict[str, Any]:
    state = dict(raw_state or {})
    default = _default_state()
    state.setdefault("schema_version", default["schema_version"])
    state.setdefault("last_run_utc", "")
    merged_subsystems: dict[str, Any] = {}
    current = dict(state.get("subsystems") or {})
    for name, defaults in default["subsystems"].items():
        merged = dict(defaults)
        merged.update(dict(current.get(name) or {}))
        merged_subsystems[name] = merged
    state["subsystems"] = merged_subsystems
    state.setdefault("latest_report", {})
    return state


def zero_engine_status(cwd: str) -> dict[str, Any]:
    boot_state_registry(cwd)
    state = _normalize_state(get_state_store(cwd, "zero_engine_status", _default_state()))
    return {
        "ok": True,
        "adapter_count": len(zero_engine_adapters()),
        "adapter_names": [adapter.name for adapter in zero_engine_adapters()],
        "path": str(_engine_path(cwd)),
        **state,
    }


def zero_engine_tick(cwd: str, *, force: bool = False, runtime_context: dict[str, Any] | None = None) -> dict[str, Any]:
    boot_state_registry(cwd)
    adapters = list(zero_engine_adapters())
    state = _normalize_state(get_state_store(cwd, "zero_engine_status", _default_state()))
    subsystems = dict(state.get("subsystems") or {})

    scan_started = perf_counter()
    scan_snapshot = build_workspace_scan_snapshot(cwd, force=force)
    scan_summary = workspace_scan_summary(scan_snapshot)
    facts: dict[str, Any] = {}
    scan_errors: dict[str, Any] = {}
    with ThreadPoolExecutor(max_workers=max(1, len(adapters))) as executor:
        futures = {
            executor.submit(adapter.scan, cwd, scan_snapshot): adapter.name
            for adapter in adapters
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

    for adapter in adapters:
        name = adapter.name
        subsystem_state = dict(subsystems.get(name) or {})
        decision = dict(decisions.get(name) or {})
        interval_seconds = int(subsystem_state.get("interval_seconds", adapter.interval_seconds) or adapter.interval_seconds)
        subsystem_state["interval_seconds"] = interval_seconds
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
            subsystems[name] = subsystem_state
            continue
        result = adapter.enforce(cwd, decision, dict(facts.get(name) or {}))
        subsystem_state["last_run_utc"] = now_utc
        subsystem_state["last_decision"] = decision
        subsystem_state["last_result"] = result
        subsystem_state["last_reason"] = str(decision.get("reason", ""))
        subsystems[name] = subsystem_state
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
        "subsystem_count": len(adapters),
        "adapter_count": len(adapters),
        "adapter_names": [adapter.name for adapter in adapters],
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
    state["schema_version"] = 2
    state["last_run_utc"] = now_utc
    state["subsystems"] = subsystems
    state["latest_report"] = report

    update_state_store(cwd, "zero_engine_status", lambda current: dict(state))
    flush_state_registry(cwd, names=["zero_engine_status", "workspace_scan_snapshot"])
    return {
        "ok": True,
        "adapter_count": len(adapters),
        "adapter_names": [adapter.name for adapter in adapters],
        "path": str(_engine_path(cwd)),
        **state,
    }
