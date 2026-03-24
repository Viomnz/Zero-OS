from __future__ import annotations

from typing import Any

from zero_os.zero_engine_adapters import zero_engine_adapters


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


def decide_zero_engine(cwd: str, facts: dict[str, Any], *, runtime_context: dict[str, Any] | None = None) -> dict[str, Any]:
    runtime_context = dict(runtime_context or {})
    decisions: dict[str, Any] = {}
    for adapter in zero_engine_adapters():
        decisions[adapter.name] = adapter.decide(cwd, dict(facts.get(adapter.name) or {}), runtime_context=runtime_context)
    priority = {
        "hold_for_review": 4,
        "failover_apply": 3,
        "backup": 2,
        "revalidate": 1,
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
        "adapter_count": len(decisions),
        "decisions": decisions,
        "next_priority_subsystem": str(next_subsystem[0]),
        "next_priority_action": str(next_subsystem[1].get("action", "observe")),
        "next_priority_reason": str(next_subsystem[1].get("reason", "")),
    }
