from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from zero_os.contradiction_engine import contradiction_engine_status
from zero_os.decision_engine import decide_maintenance_action
from zero_os.flow_monitor import flow_scan, flow_status
from zero_os.phase_runtime import zero_ai_runtime_run, zero_ai_runtime_status
from zero_os.recovery import zero_ai_backup_status
from zero_os.self_repair import self_repair_status
from zero_os.state_cache import flush_state_writes, load_json_state, queue_json_state
from zero_os.state_registry import put_state_store
from zero_os.zero_ai_control_workflows import zero_ai_control_workflow_self_repair, zero_ai_control_workflows_status


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _assistant_dir(cwd: str) -> Path:
    path = Path(cwd).resolve() / ".zero_os" / "assistant"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _path(cwd: str) -> Path:
    return _assistant_dir(cwd) / "maintenance_orchestrator.json"


def _load(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    raw = load_json_state(path, default)
    if not isinstance(raw, dict):
        return dict(default)
    merged = dict(default)
    merged.update(raw)
    return merged


def _save(path: Path, payload: dict[str, Any]) -> None:
    queue_json_state(path, payload)


def _default_state() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "last_run_utc": "",
        "last_action": "observe",
        "last_status": "missing",
        "last_reason": "",
        "last_report": {},
        "history": [],
    }


def _snapshot(cwd: str) -> dict[str, Any]:
    from zero_os.zero_ai_pressure_harness import pressure_harness_status
    from zero_os.self_derivation_engine import self_derivation_status

    return {
        "runtime": zero_ai_runtime_status(cwd),
        "flow": flow_status(cwd),
        "pressure": pressure_harness_status(cwd),
        "self_derivation": self_derivation_status(cwd),
        "contradiction": contradiction_engine_status(cwd),
        "workflows": zero_ai_control_workflows_status(cwd),
        "backups": zero_ai_backup_status(cwd),
        "self_repair": self_repair_status(cwd),
    }


def _next_action(snapshot: dict[str, Any]) -> dict[str, Any]:
    return decide_maintenance_action(snapshot)


def _highest_value_steps(snapshot: dict[str, Any], next_action: dict[str, Any]) -> list[str]:
    steps: list[str] = []
    runtime = dict(snapshot.get("runtime") or {})
    flow = dict(snapshot.get("flow") or {})
    pressure = dict(snapshot.get("pressure") or {})
    self_derivation = dict(snapshot.get("self_derivation") or {})
    contradiction = dict(snapshot.get("contradiction") or {})
    backups = dict(snapshot.get("backups") or {})

    continuity = dict(contradiction.get("continuity") or {})
    if bool(continuity.get("has_contradiction", False)):
        steps.append("Resolve self contradiction before allowing broader auto-maintenance.")
    if bool(runtime.get("missing", False)) or not bool(runtime.get("runtime_ready", False)):
        steps.append("Run the phase runtime so maintenance has a healthy control plane.")
    if float(((flow.get("summary") or {}).get("flow_score", 0.0)) or 0.0) < 100.0:
        steps.append("Lift the flow score back to 100 by repairing the failing health or execution lane.")
    if bool(pressure.get("missing", False)) or float(pressure.get("overall_score", 0.0) or 0.0) < 100.0:
        steps.append("Refresh the pressure harness so auto-maintenance is driven by current survivability evidence.")
    if int(self_derivation.get("revalidation_ready_count", 0) or 0) > 0:
        steps.append("Run bounded self-derivation revalidation so ready quarantined strategies can re-earn trust under the current planner generation.")
    if int(backups.get("snapshot_count", 0) or 0) == 0:
        steps.append("Create a recovery snapshot baseline before widening maintenance autonomy.")
    if not steps:
        steps.append(str(next_action.get("summary", "Maintain the current clean maintenance baseline.")))
    return steps


def maintenance_status(cwd: str) -> dict[str, Any]:
    snapshot = _snapshot(cwd)
    next_action = _next_action(snapshot)
    state = _load(_path(cwd), _default_state())
    return {
        "ok": True,
        "path": str(_path(cwd)),
        "active": True,
        "ready": True,
        "last_run_utc": str(state.get("last_run_utc", "")),
        "last_action": str(state.get("last_action", "observe")),
        "last_status": str(state.get("last_status", "missing")),
        "next_action": next_action,
        "highest_value_steps": _highest_value_steps(snapshot, next_action),
        "snapshot": snapshot,
    }


def maintenance_run(cwd: str) -> dict[str, Any]:
    before = _snapshot(cwd)
    next_action = _next_action(before)
    action = str(next_action.get("action", "observe"))

    if action == "runtime_run":
        action_result = zero_ai_runtime_run(cwd)
    elif action == "self_repair":
        action_result = zero_ai_control_workflow_self_repair(cwd)
    elif action == "pressure_run":
        from zero_os.zero_ai_pressure_harness import pressure_harness_run

        action_result = pressure_harness_run(cwd)
    elif action == "self_derivation_revalidate":
        from zero_os.self_derivation_engine import self_derivation_revalidate

        action_result = self_derivation_revalidate(cwd)
    else:
        if bool((before.get("flow") or {}).get("last_scan_utc", "")):
            action_result = flow_status(cwd)
        else:
            action_result = flow_scan(cwd, "src")

    after = _snapshot(cwd)
    report = {
        "ok": bool(action_result.get("ok", False)),
        "time_utc": _utc_now(),
        "action": action,
        "reason": str(next_action.get("reason", "")),
        "summary": str(next_action.get("summary", "")),
        "action_result": action_result,
        "before": before,
        "after": after,
        "highest_value_steps": _highest_value_steps(after, _next_action(after)),
    }
    state = _load(_path(cwd), _default_state())
    state["last_run_utc"] = report["time_utc"]
    state["last_action"] = action
    state["last_status"] = "ok" if report["ok"] else "attention"
    state["last_reason"] = report["reason"]
    state["last_report"] = report
    history = list(state.get("history", []))
    history.append({"time_utc": report["time_utc"], "action": action, "ok": report["ok"], "reason": report["reason"]})
    state["history"] = history[-20:]
    put_state_store(cwd, "maintenance_state", state)
    _save(_path(cwd), state)
    flush_state_writes(paths=[_path(cwd)])
    report["path"] = str(_path(cwd))
    return report


def maintenance_refresh(cwd: str) -> dict[str, Any]:
    return maintenance_status(cwd)
