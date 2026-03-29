from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from zero_os.calendar_time import calendar_reminder_tick
from zero_os.communications import communications_tick
from zero_os.contradiction_engine import contradiction_engine_status
from zero_os.self_derivation_engine import self_derivation_revalidate, self_derivation_status
from zero_os.subsystem_executor import execute_subsystem_adapters
from zero_os.zero_engine import execute_zero_engine_plane
from zero_os.zero_engine_adapters import zero_engine_adapters
from zero_os.zero_ai_autonomy import (
    zero_ai_autonomy_loop_status,
    zero_ai_autonomy_loop_tick,
    zero_ai_autonomy_sync,
)
from zero_os.zero_ai_capability_map import zero_ai_capability_map_status
from zero_os.zero_ai_control_workflows import zero_ai_control_workflows_status
from zero_os.zero_ai_evolution import zero_ai_evolution_status
from zero_os.zero_ai_pressure_harness import pressure_harness_status
from zero_os.zero_ai_source_evolution import zero_ai_source_evolution_status
from zero_os.subsystem_registry import (
    register_subsystem_adapter,
    subsystem_adapter_map,
    subsystem_adapters,
    unregister_subsystem_adapter,
)


def _noop_background(reason: str) -> dict[str, Any]:
    return {"ok": True, "ran": False, "reason": str(reason)}


@dataclass(frozen=True)
class RuntimeSubsystemAdapter:
    name: str
    order: int
    run: Callable[[str, dict[str, Any]], dict[str, Any]]


def _run_autonomy(cwd: str, context: dict[str, Any]) -> dict[str, Any]:
    autonomy = zero_ai_autonomy_sync(cwd)
    autonomy_loop = zero_ai_autonomy_loop_status(cwd)
    if bool(context.get("skip_autonomy_background", False)):
        autonomy_background = {
            "ok": True,
            "ran": False,
            "reason": "autonomy background skipped by runtime context",
            "autonomy_loop": autonomy_loop,
        }
    elif bool(autonomy_loop.get("enabled", False)):
        autonomy_background = zero_ai_autonomy_loop_tick(cwd)
    else:
        autonomy_background = {
            "ok": True,
            "ran": False,
            "reason": "autonomy loop is off",
            "autonomy_loop": autonomy_loop,
        }
    return {
        "updates": {
            "autonomy": autonomy.get("status", {}),
            "autonomy_background": autonomy_background,
        },
        "runtime_checks": {
            "autonomy_goal_manager": bool(autonomy.get("ok", False)),
            "autonomy_loop_state": bool(autonomy_loop.get("ok", False)),
            "autonomy_background": bool(autonomy_background.get("ok", False)),
        },
        "context": {
            "autonomy": autonomy,
            "autonomy_loop": autonomy_loop,
        },
    }


def _run_communications(cwd: str, context: dict[str, Any]) -> dict[str, Any]:
    background = communications_tick(cwd)
    return {
        "updates": {"communications_background": background},
        "runtime_checks": {"communications_background": bool(background.get("ok", False))},
    }


def _run_calendar(cwd: str, context: dict[str, Any]) -> dict[str, Any]:
    background = calendar_reminder_tick(cwd)
    return {
        "updates": {"calendar_time_background": background},
        "runtime_checks": {"calendar_time_background": bool(background.get("ok", False))},
    }


def _run_contradiction(cwd: str, context: dict[str, Any]) -> dict[str, Any]:
    contradiction = contradiction_engine_status(cwd)
    continuity = dict(contradiction.get("continuity") or {})
    continuity_ready = bool(continuity.get("same_system", False)) and not bool(continuity.get("has_contradiction", False))
    return {
        "context": {
            "contradiction": contradiction,
            "continuity": continuity,
            "continuity_ready": continuity_ready,
        }
    }


def _run_pressure(cwd: str, context: dict[str, Any]) -> dict[str, Any]:
    pressure = pressure_harness_status(cwd)
    pressure_score = float(pressure.get("overall_score", 0.0) or 0.0)
    pressure_ready = not bool(pressure.get("missing", False)) and pressure_score >= 100.0
    return {
        "context": {
            "pressure": pressure,
            "pressure_score": pressure_score,
            "pressure_ready": pressure_ready,
        }
    }


def _run_self_derivation(cwd: str, context: dict[str, Any]) -> dict[str, Any]:
    derivation_before = self_derivation_status(cwd)
    revalidation_ready_count = int(derivation_before.get("revalidation_ready_count", 0) or 0)
    pressure = dict(context.get("pressure") or {})
    continuity = dict(context.get("continuity") or {})
    pressure_score = float(context.get("pressure_score", 0.0) or 0.0)
    pressure_ready = bool(context.get("pressure_ready", False))
    continuity_ready = bool(context.get("continuity_ready", False))
    if revalidation_ready_count > 0 and pressure_ready and continuity_ready:
        background = dict(self_derivation_revalidate(cwd, limit=min(3, revalidation_ready_count)))
        background.setdefault("ran", True)
    else:
        reasons: list[str] = []
        if revalidation_ready_count <= 0:
            reasons.append("no strategies ready for revalidation")
        if not pressure_ready:
            reasons.append("pressure baseline not ready")
        if not continuity_ready:
            reasons.append("continuity not ready")
        background = {
            "ok": True,
            "ran": False,
            "reason": "; ".join(reasons) or "self derivation revalidation skipped",
            "revalidation_ready_count": revalidation_ready_count,
            "pressure_missing": bool(pressure.get("missing", False)),
            "pressure_score": pressure_score,
            "continuity": continuity,
        }
    derivation_after = self_derivation_status(cwd)
    return {
        "updates": {
            "self_derivation": derivation_after,
            "self_derivation_background": background,
        },
        "runtime_checks": {
            "self_derivation_engine": bool(derivation_after.get("ok", False)),
            "self_derivation_background": bool(background.get("ok", False)),
        },
        "context": {
            "self_derivation": derivation_after,
            "self_derivation_background": background,
        },
    }


def _run_control_workflows(cwd: str, context: dict[str, Any]) -> dict[str, Any]:
    status = zero_ai_control_workflows_status(cwd)
    return {
        "updates": {"control_workflows": status},
        "runtime_checks": {"control_workflows": bool(status.get("ok", False))},
    }


def _run_capability_map(cwd: str, context: dict[str, Any]) -> dict[str, Any]:
    status = zero_ai_capability_map_status(cwd)
    return {
        "updates": {"capability_control_map": status},
        "runtime_checks": {"capability_control_map": bool(status.get("ok", False))},
    }


def _run_evolution(cwd: str, context: dict[str, Any]) -> dict[str, Any]:
    status = zero_ai_evolution_status(cwd)
    return {
        "updates": {"evolution": status},
        "runtime_checks": {"evolution_engine": bool(status.get("ok", False))},
    }


def _run_source_evolution(cwd: str, context: dict[str, Any]) -> dict[str, Any]:
    status = zero_ai_source_evolution_status(cwd)
    return {
        "updates": {"source_evolution": status},
        "runtime_checks": {"source_evolution_engine": bool(status.get("ok", False))},
    }


def register_runtime_subsystem_adapter(adapter: RuntimeSubsystemAdapter, *, replace: bool = False) -> RuntimeSubsystemAdapter:
    return register_subsystem_adapter("runtime", adapter, replace=replace)


def runtime_subsystem_adapter_map() -> dict[str, RuntimeSubsystemAdapter]:
    return dict(subsystem_adapter_map("runtime"))


def unregister_runtime_subsystem_adapter(name: str) -> RuntimeSubsystemAdapter | None:
    return unregister_subsystem_adapter("runtime", name)


def _install_builtin_runtime_adapters() -> None:
    if runtime_subsystem_adapter_map():
        return
    register_runtime_subsystem_adapter(RuntimeSubsystemAdapter(name="autonomy", order=10, run=_run_autonomy))
    register_runtime_subsystem_adapter(RuntimeSubsystemAdapter(name="communications", order=20, run=_run_communications))
    register_runtime_subsystem_adapter(RuntimeSubsystemAdapter(name="calendar_time", order=30, run=_run_calendar))
    register_runtime_subsystem_adapter(RuntimeSubsystemAdapter(name="contradiction", order=40, run=_run_contradiction))
    register_runtime_subsystem_adapter(RuntimeSubsystemAdapter(name="pressure", order=50, run=_run_pressure))
    register_runtime_subsystem_adapter(RuntimeSubsystemAdapter(name="self_derivation", order=60, run=_run_self_derivation))
    register_runtime_subsystem_adapter(RuntimeSubsystemAdapter(name="control_workflows", order=70, run=_run_control_workflows))
    register_runtime_subsystem_adapter(RuntimeSubsystemAdapter(name="capability_control_map", order=80, run=_run_capability_map))
    register_runtime_subsystem_adapter(RuntimeSubsystemAdapter(name="evolution", order=90, run=_run_evolution))
    register_runtime_subsystem_adapter(RuntimeSubsystemAdapter(name="source_evolution", order=100, run=_run_source_evolution))


def runtime_subsystem_adapters() -> tuple[RuntimeSubsystemAdapter, ...]:
    _install_builtin_runtime_adapters()
    return tuple(subsystem_adapters("runtime", key=lambda adapter: (adapter.order, adapter.name)))


def run_runtime_subsystems(cwd: str, *, context: dict[str, Any] | None = None, force: bool = False) -> dict[str, Any]:
    runtime_execution = execute_subsystem_adapters(cwd, runtime_subsystem_adapters(), context=context)
    execution_context = dict(runtime_execution.get("context") or {})
    zero_engine_execution = execute_zero_engine_plane(
        cwd,
        force=force,
        runtime_context={
            "pressure_ready": bool(execution_context.get("pressure_ready", False)),
            "pressure_score": float(execution_context.get("pressure_score", 0.0) or 0.0),
            "continuity_ready": bool(execution_context.get("continuity_ready", False)),
            "continuity": dict(execution_context.get("continuity") or {}),
        },
        persist=False,
    )
    zero_engine_report = dict(zero_engine_execution.get("latest_report") or {})
    updates = dict(runtime_execution.get("updates") or {})
    updates["zero_engine"] = dict(zero_engine_execution)
    updates["zero_engine_background"] = zero_engine_report
    runtime_checks = dict(runtime_execution.get("runtime_checks") or {})
    runtime_checks["zero_engine"] = bool(zero_engine_execution.get("ok", False))
    runtime_checks["zero_engine_background"] = bool(zero_engine_report.get("ok", False))
    execution_context["zero_engine"] = dict(zero_engine_execution)
    execution_context["zero_engine_background"] = zero_engine_report
    runtime_names = list(runtime_execution.get("adapter_names") or [])
    zero_engine_names = [f"zero_engine:{name}" for name in list(zero_engine_execution.get("adapter_names") or [])]
    return {
        "ok": True,
        "mode": "universal",
        "scheduler": "flattened",
        "runtime_adapter_count": int(runtime_execution.get("adapter_count", 0) or 0),
        "decision_adapter_count": len(zero_engine_adapters()),
        "adapter_count": int(runtime_execution.get("adapter_count", 0) or 0) + len(zero_engine_adapters()),
        "adapter_names": runtime_names + zero_engine_names,
        "runtime_adapter_names": runtime_names,
        "decision_adapter_names": zero_engine_names,
        "updates": updates,
        "runtime_checks": runtime_checks,
        "context": execution_context,
        "adapter_results": dict(runtime_execution.get("adapter_results") or {}),
        "zero_engine_execution": dict(zero_engine_execution),
        "state_updates": {
            "zero_engine_status": dict(zero_engine_execution),
            "workspace_scan_snapshot": dict(zero_engine_execution.get("scan_snapshot_payload") or {}),
        },
    }


_install_builtin_runtime_adapters()
