from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from zero_os.calendar_time import calendar_reminder_tick
from zero_os.communications import communications_tick
from zero_os.contradiction_engine import contradiction_engine_status
from zero_os.self_derivation_engine import self_derivation_revalidate, self_derivation_status
from zero_os.zero_engine import zero_engine_status, zero_engine_tick
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


def _run_zero_engine(cwd: str, context: dict[str, Any]) -> dict[str, Any]:
    background = zero_engine_tick(
        cwd,
        runtime_context={
            "pressure_ready": bool(context.get("pressure_ready", False)),
            "pressure_score": float(context.get("pressure_score", 0.0) or 0.0),
            "continuity_ready": bool(context.get("continuity_ready", False)),
            "continuity": dict(context.get("continuity") or {}),
        },
    )
    status = zero_engine_status(cwd)
    return {
        "updates": {
            "zero_engine": status,
            "zero_engine_background": background,
        },
        "runtime_checks": {
            "zero_engine": bool(status.get("ok", False)),
            "zero_engine_background": bool(background.get("ok", False)),
        },
        "context": {
            "zero_engine": status,
            "zero_engine_background": background,
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


_ADAPTERS: tuple[RuntimeSubsystemAdapter, ...] = (
    RuntimeSubsystemAdapter(name="autonomy", order=10, run=_run_autonomy),
    RuntimeSubsystemAdapter(name="communications", order=20, run=_run_communications),
    RuntimeSubsystemAdapter(name="calendar_time", order=30, run=_run_calendar),
    RuntimeSubsystemAdapter(name="contradiction", order=40, run=_run_contradiction),
    RuntimeSubsystemAdapter(name="pressure", order=50, run=_run_pressure),
    RuntimeSubsystemAdapter(name="self_derivation", order=60, run=_run_self_derivation),
    RuntimeSubsystemAdapter(name="zero_engine", order=70, run=_run_zero_engine),
    RuntimeSubsystemAdapter(name="control_workflows", order=80, run=_run_control_workflows),
    RuntimeSubsystemAdapter(name="capability_control_map", order=90, run=_run_capability_map),
    RuntimeSubsystemAdapter(name="evolution", order=100, run=_run_evolution),
    RuntimeSubsystemAdapter(name="source_evolution", order=110, run=_run_source_evolution),
)


def runtime_subsystem_adapters() -> tuple[RuntimeSubsystemAdapter, ...]:
    return tuple(sorted(_ADAPTERS, key=lambda adapter: (adapter.order, adapter.name)))


def run_runtime_subsystems(cwd: str, *, context: dict[str, Any] | None = None) -> dict[str, Any]:
    shared_context = dict(context or {})
    updates: dict[str, Any] = {}
    runtime_checks: dict[str, Any] = {}
    adapter_results: dict[str, Any] = {}
    for adapter in runtime_subsystem_adapters():
        result = dict(adapter.run(cwd, shared_context) or {})
        adapter_results[adapter.name] = result
        updates.update(dict(result.get("updates") or {}))
        runtime_checks.update(dict(result.get("runtime_checks") or {}))
        shared_context.update(dict(result.get("context") or {}))
    return {
        "ok": True,
        "adapter_count": len(runtime_subsystem_adapters()),
        "adapter_names": [adapter.name for adapter in runtime_subsystem_adapters()],
        "updates": updates,
        "runtime_checks": runtime_checks,
        "context": shared_context,
        "adapter_results": adapter_results,
    }
