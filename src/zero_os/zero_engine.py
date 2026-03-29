from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from zero_os.decision_engine import decide_zero_engine, zero_engine_action_is_mutating
from zero_os.scan_coordinator import build_workspace_scan_snapshot, workspace_scan_summary
from zero_os.state_registry import (
    boot_state_registry,
    commit_state_transaction,
    get_state_store,
)
from zero_os.subsystem_executor import execute_subsystem_adapters
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


def execute_zero_engine_plane(
    cwd: str,
    *,
    force: bool = False,
    runtime_context: dict[str, Any] | None = None,
    persist: bool = False,
) -> dict[str, Any]:
    boot_state_registry(cwd)
    adapters = list(zero_engine_adapters())
    state = _normalize_state(get_state_store(cwd, "zero_engine_status", _default_state()))
    subsystems = dict(state.get("subsystems") or {})

    scan_snapshot = build_workspace_scan_snapshot(cwd, force=force)
    scan_summary = workspace_scan_summary(scan_snapshot)
    execution = execute_subsystem_adapters(
        cwd,
        adapters,
        context=runtime_context,
        force=force,
        subsystem_state=subsystems,
        scan_snapshot=scan_snapshot,
        decide_all=lambda exec_cwd, exec_facts, exec_context: decide_zero_engine(
            exec_cwd,
            exec_facts,
            runtime_context=exec_context,
        ),
        due_predicate=lambda last_run_utc, interval_seconds, force_run: _due(
            last_run_utc,
            interval_seconds,
            force=force_run,
        ),
        mutation_action_predicate=zero_engine_action_is_mutating,
    )
    decisions = dict(execution.get("decisions") or {})
    subsystem_reports = dict(execution.get("subsystem_reports") or {})
    now_utc = str(execution.get("generated_utc", _utc_now()))
    scan_duration_ms = round(float(execution.get("scan_duration_ms", 0.0) or 0.0), 3)
    scan_errors = dict(execution.get("scan_errors") or {})
    ran_count = int(execution.get("ran_count", 0) or 0)
    executed_mutation_count = int(execution.get("executed_mutation_count", 0) or 0)
    deferred_mutation_count = int(execution.get("deferred_mutation_count", 0) or 0)
    mutation_winner_name = str(execution.get("mutation_winner_subsystem", "") or "")
    decision_block = dict(execution.get("decision_block") or {})
    subsystems = dict(execution.get("updated_subsystems") or {})

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
        "mutation_budget": {
            "limit": 1,
            "candidate_count": int(execution.get("due_mutating_candidate_count", 0) or 0),
            "recommended_winner_subsystem": str(dict(decision_block.get("mutation_budget") or {}).get("winner_subsystem", "")),
            "recommended_winner_action": str(dict(decision_block.get("mutation_budget") or {}).get("winner_action", "")),
            "applied_winner_subsystem": mutation_winner_name,
            "executed_mutation_count": executed_mutation_count,
            "deferred_mutation_count": deferred_mutation_count,
        },
        "scan_mode": "parallel",
        "executor": "universal",
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
    result = {
        "ok": True,
        "adapter_count": len(adapters),
        "adapter_names": [adapter.name for adapter in adapters],
        "path": str(_engine_path(cwd)),
        "scan_snapshot_payload": dict(scan_snapshot),
        "scan_snapshot_summary": scan_summary,
        **state,
    }
    if persist:
        commit_id = f"zero-engine-{uuid4()}"
        result["control_plane_commit_id"] = commit_id
        result["latest_report"]["control_plane_commit_id"] = commit_id
        persisted_state = dict(result)
        persisted_state.pop("scan_snapshot_payload", None)
        persisted_state.pop("scan_snapshot_summary", None)
        transaction = commit_state_transaction(
            cwd,
            {
                "zero_engine_status": persisted_state,
                "workspace_scan_snapshot": dict(scan_snapshot),
            },
            label="zero_engine_tick",
            transaction_id=commit_id,
        )
        result["control_plane_commit"] = transaction
    return result


def zero_engine_tick(cwd: str, *, force: bool = False, runtime_context: dict[str, Any] | None = None) -> dict[str, Any]:
    return execute_zero_engine_plane(cwd, force=force, runtime_context=runtime_context, persist=True)
