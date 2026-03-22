from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from zero_os.internet_capability import internet_capability_status
from zero_os.maintenance_orchestrator import maintenance_status
from zero_os.zero_ai_capability_map import zero_ai_capability_map_status


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _assistant_dir(cwd: str) -> Path:
    path = Path(cwd).resolve() / ".zero_os" / "assistant"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _path(cwd: str) -> Path:
    return _assistant_dir(cwd) / "world_class_readiness.json"


def _save(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _grade(score: float) -> str:
    if score >= 95.0:
        return "A"
    if score >= 85.0:
        return "B"
    if score >= 75.0:
        return "C"
    if score >= 65.0:
        return "D"
    return "F"


def _lane(score: float, summary: str, blockers: list[str]) -> dict[str, Any]:
    return {"score": round(score, 2), "summary": summary, "blockers": blockers}


def world_class_readiness_status(cwd: str) -> dict[str, Any]:
    from zero_os.zero_ai_pressure_harness import pressure_harness_status

    capability_map = zero_ai_capability_map_status(cwd)
    pressure = pressure_harness_status(cwd)
    maintenance = maintenance_status(cwd)
    internet = internet_capability_status(cwd)

    cap_summary = dict(capability_map.get("summary") or {})
    reliability_score = float(pressure.get("overall_score", 0.0) or 0.0)
    reliability_blockers: list[str] = []
    if bool(pressure.get("missing", False)):
        reliability_blockers.append("pressure_baseline_missing")
    if int(pressure.get("failed_count", 0) or 0) > 0:
        reliability_blockers.append(str(pressure.get("top_failure_code", "pressure_failures")))

    autonomous_count = int(cap_summary.get("autonomous_count", 0) or 0)
    active_autonomous_count = int(cap_summary.get("active_autonomous_count", 0) or 0)
    planner_history_count = int(cap_summary.get("planner_feedback_history_count", 0) or 0)
    planner_route_quality_score = float(cap_summary.get("planner_route_quality_score", 100.0) or 100.0)
    planner_worst_route = str(cap_summary.get("planner_feedback_worst_route", "") or "")
    planner_target_drop_rate = float(cap_summary.get("planner_feedback_target_drop_rate", 0.0) or 0.0)
    planner_hold_rate = float(cap_summary.get("planner_feedback_contradiction_hold_rate", 0.0) or 0.0)
    control_score = round((active_autonomous_count / max(1, autonomous_count)) * 100.0, 2)
    control_blockers: list[str] = []
    if int(cap_summary.get("approval_gated_count", 0) or 0) > 0:
        control_blockers.append("approval_gated_capabilities")

    execution_score = 100.0 if bool((internet.get("summary") or {}).get("internet_ready", False)) else 60.0
    execution_blockers: list[str] = []
    if not bool((internet.get("browser") or {}).get("connected", False)):
        execution_blockers.append("browser_surface_cold")
    if int((internet.get("api_profiles") or {}).get("count", 0) or 0) == 0:
        execution_blockers.append("typed_api_surface_missing")

    maintenance_action = dict(maintenance.get("next_action") or {})
    evidence_score = 100.0 if maintenance_action.get("reason") == "stable" else 75.0
    evidence_blockers: list[str] = []
    if str(maintenance_action.get("reason", "")) not in {"stable", ""}:
        evidence_blockers.append(str(maintenance_action.get("reason", "")))
    if bool(pressure.get("missing", False)):
        evidence_blockers.append("pressure_evidence_missing")
    if planner_history_count > 0:
        evidence_score = round((evidence_score * 0.7) + (planner_route_quality_score * 0.3), 2)
        if planner_route_quality_score < 85.0:
            evidence_blockers.append("planner_route_drift")

    lanes = {
        "reliability": _lane(reliability_score, "Pressure, contradiction, and task survivability under bounded stress.", reliability_blockers),
        "control": _lane(control_score, "Typed autonomy, approvals, and bounded control semantics.", control_blockers),
        "execution": _lane(execution_score, "Browser, internet, and typed external execution surfaces.", execution_blockers),
        "evidence": _lane(evidence_score, "Maintenance truthfulness, operational visibility, and live readiness evidence.", evidence_blockers),
    }
    overall_score = round(sum(lane["score"] for lane in lanes.values()) / max(1, len(lanes)), 2)

    blocker_pairs = [(name, lane["blockers"]) for name, lane in lanes.items() if lane["blockers"]]
    top_gap = blocker_pairs[0][1][0] if blocker_pairs else "none"
    if top_gap == "pressure_baseline_missing":
        highest_value_step = "Run the pressure harness and keep collecting survivability evidence before claiming world-class reliability."
    elif top_gap == "browser_surface_cold":
        highest_value_step = "Use the browser lane on real tasks so execution evidence is based on live browsing, not only capability claims."
    elif top_gap == "typed_api_surface_missing":
        highest_value_step = "Add more typed API profiles so Zero AI can operate across real external systems with stronger evidence."
    elif top_gap == "approval_gated_capabilities":
        highest_value_step = "Keep converting high-value lanes into bounded typed workflows without dropping safety gates."
    elif top_gap == "planner_route_drift":
        highest_value_step = f"Improve planner route quality on `{planner_worst_route or 'the weakest route'}` before widening more autonomous execution."
    elif top_gap == "stable":
        highest_value_step = "Keep running real work through Zero AI and measure long-run survival."
    else:
        highest_value_step = "Keep running real work through Zero AI and fix the weakest measured lane first."

    payload = {
        "ok": True,
        "time_utc": _utc_now(),
        "overall_score": overall_score,
        "grade": _grade(overall_score),
        "world_class_now": overall_score >= 95.0 and not blocker_pairs,
        "top_gap": top_gap,
        "highest_value_step": highest_value_step,
        "lanes": lanes,
        "inputs": {
            "pressure_score": reliability_score,
            "autonomous_surface_score": float(cap_summary.get("autonomous_surface_score", 0.0) or 0.0),
            "active_autonomous_surface_score": float(cap_summary.get("active_autonomous_surface_score", 0.0) or 0.0),
            "autonomous_count": autonomous_count,
            "active_autonomous_count": active_autonomous_count,
            "forbidden_surface_count": int(cap_summary.get("forbidden_count", 0) or 0),
            "internet_connected_surface_count": int((internet.get("summary") or {}).get("connected_surface_count", 0) or 0),
            "maintenance_reason": str(maintenance_action.get("reason", "")),
            "planner_feedback_history_count": planner_history_count,
            "planner_route_quality_score": planner_route_quality_score,
            "planner_feedback_worst_route": planner_worst_route,
            "planner_feedback_target_drop_rate": planner_target_drop_rate,
            "planner_feedback_contradiction_hold_rate": planner_hold_rate,
        },
        "highest_value_steps": [highest_value_step],
        "path": str(_path(cwd)),
    }
    _save(_path(cwd), payload)
    return payload


def world_class_readiness_refresh(cwd: str) -> dict[str, Any]:
    return world_class_readiness_status(cwd)
