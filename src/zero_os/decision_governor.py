from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from zero_os.world_model import world_model_status


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def governor_decide(cwd: str, *, world_model: dict[str, Any] | None = None) -> dict[str, Any]:
    model = dict(world_model or world_model_status(cwd) or {})
    if model.get("missing", False) or not model.get("ok", True):
        return {
            "ok": True,
            "time_utc": _utc_now(),
            "call": "observe",
            "mode": "conservative",
            "priority": 20,
            "confidence": 0.4,
            "reason": "world model is missing, so the safest call is observation",
            "blocking_factors": [],
            "observed": {
                "runtime_ready": False,
                "runtime_missing": True,
                "same_system": False,
                "has_contradiction": False,
                "approvals_pending": 0,
                "jobs_pending": 0,
                "pressure_ready": False,
                "recovery_ready": False,
                "recovery_snapshot_count": 0,
                "recovery_compatible_count": 0,
                "revalidation_ready_count": 0,
                "requested_code_mutation": False,
                "code_scope_ready": False,
                "code_verification_ready": False,
                "code_verification_surface_ready": False,
                "code_dirty_worktree": False,
                "code_dirty_in_scope_count": 0,
                "code_source_canary_ready": False,
                "goal_count": 0,
                "open_goal_count": 0,
                "blocked_goal_count": 0,
                "current_goal_title": "",
                "goal_loop_due_now": False,
                "observation_blocking_event_count": 0,
                "causal_action_bias": "observe",
                "stale_domains": [],
            },
        }
    if bool(model.get("stale", False)) and not bool(model.get("fresh_enough", True)):
        stale_domains = [str(item) for item in list(model.get("stale_domains", [])) if str(item)]
        return {
            "ok": True,
            "time_utc": _utc_now(),
            "call": "run_runtime",
            "mode": "safe",
            "priority": 90,
            "confidence": 0.88,
            "reason": "world model is stale, so runtime truth must be refreshed before autonomous action",
            "blocking_factors": stale_domains,
            "observed": {
                "runtime_ready": False,
                "runtime_missing": False,
                "same_system": False,
                "has_contradiction": False,
                "approvals_pending": 0,
                "jobs_pending": 0,
                "pressure_ready": False,
                "recovery_ready": False,
                "recovery_snapshot_count": 0,
                "recovery_compatible_count": 0,
                "revalidation_ready_count": 0,
                "requested_code_mutation": False,
                "code_scope_ready": False,
                "code_verification_ready": False,
                "code_verification_surface_ready": False,
                "code_dirty_worktree": False,
                "code_dirty_in_scope_count": 0,
                "code_source_canary_ready": False,
                "goal_count": 0,
                "open_goal_count": 0,
                "blocked_goal_count": 0,
                "current_goal_title": "",
                "goal_loop_due_now": False,
                "observation_blocking_event_count": 0,
                "causal_action_bias": "run_runtime",
                "stale_domains": stale_domains,
            },
        }
    domains = dict(model.get("domains") or {})
    runtime = dict((domains.get("runtime") or {}).get("summary") or {})
    continuity = dict((domains.get("continuity") or {}).get("summary") or {})
    pressure = dict((domains.get("pressure") or {}).get("summary") or {})
    recovery = dict((domains.get("recovery") or {}).get("summary") or {})
    approvals = dict((domains.get("approvals") or {}).get("summary") or {})
    jobs = dict((domains.get("jobs") or {}).get("summary") or {})
    self_derivation = dict((domains.get("self_derivation") or {}).get("summary") or {})
    evolution = dict((domains.get("evolution") or {}).get("summary") or {})
    source_evolution = dict((domains.get("source_evolution") or {}).get("summary") or {})
    codebase = dict((domains.get("codebase") or {}).get("summary") or {})
    goals = dict((domains.get("goals") or {}).get("summary") or {})
    observation_stream = dict((domains.get("observation_stream") or {}).get("summary") or {})
    causal_assessment = dict(model.get("causal_assessment") or {})

    call = "observe"
    mode = "normal"
    priority = 10
    confidence = 0.6
    reason = "world model stable enough for observation"
    blockers: list[str] = []

    approvals_pending = int(approvals.get("pending_count", 0) or 0)
    jobs_pending = int(jobs.get("pending_count", 0) or 0)
    runtime_ready = bool(runtime.get("runtime_ready", False))
    runtime_missing = bool(runtime.get("runtime_missing", False))
    runtime_loop_enabled = bool(runtime.get("runtime_loop_enabled", False))
    runtime_agent_installed = bool(runtime.get("runtime_agent_installed", False))
    runtime_agent_running = bool(runtime.get("runtime_agent_running", False))
    same_system = bool(continuity.get("same_system", False))
    has_contradiction = bool(continuity.get("has_contradiction", False))
    pressure_ready = bool(pressure.get("pressure_ready", False))
    recovery_observed = bool(recovery.get("observed", False))
    recovery_ready = bool(recovery.get("compatible_snapshot_ready", False))
    recovery_snapshot_count = int(recovery.get("snapshot_count", 0) or 0)
    recovery_compatible_count = int(recovery.get("compatible_count", 0) or 0)
    revalidation_ready_count = int(self_derivation.get("revalidation_ready_count", 0) or 0)
    requested_code_mutation = bool(codebase.get("requested_code_mutation", False))
    code_scope_ready = bool(codebase.get("scope_ready", False))
    code_verification_ready = bool(codebase.get("verification_ready", False))
    code_verification_surface_ready = bool(codebase.get("verification_surface_ready", False))
    code_dirty_worktree = bool(codebase.get("dirty_worktree", False))
    code_dirty_in_scope_count = int(codebase.get("dirty_in_scope_count", 0) or 0)
    code_out_of_scope_count = int(codebase.get("out_of_scope_count", 0) or 0)
    code_source_canary_ready = bool(codebase.get("source_canary_ready", False))
    goal_count = int(goals.get("goal_count", 0) or 0)
    open_goal_count = int(goals.get("open_count", 0) or 0)
    blocked_goal_count = int(goals.get("blocked_count", 0) or 0)
    current_goal_title = str(goals.get("current_goal_title", "") or "")
    current_goal_requires_user = bool(goals.get("current_goal_requires_user", False))
    current_goal_state = str(goals.get("current_goal_state", "") or "")
    goal_loop_due_now = bool(goals.get("loop_due_now", False))
    observation_blocking_event_count = int(observation_stream.get("blocking_event_count", 0) or 0)
    causal_action_bias = str(causal_assessment.get("action_bias", "observe") or "observe")

    if approvals_pending > 0:
        call = "wait_for_user"
        mode = "blocked"
        priority = 110
        confidence = 1.0
        reason = "human approval is required before further autonomous action"
        blockers.append(f"{approvals_pending} approval item(s) pending")
    elif not same_system or has_contradiction:
        call = "repair_continuity"
        mode = "safe"
        priority = 100
        confidence = 0.99
        reason = "continuity drift or contradiction must be repaired before autonomous work"
        if not same_system:
            blockers.append("system continuity is not stable")
        if has_contradiction:
            blockers.append("contradiction detected")
    elif runtime_missing or not runtime_ready:
        call = "run_runtime"
        mode = "safe"
        priority = 95
        confidence = 0.98
        reason = "runtime is missing or not ready"
        blockers.append("runtime not ready")
    elif not runtime_agent_installed or not runtime_agent_running:
        call = "ensure_background_agent"
        mode = "safe"
        priority = 85
        confidence = 0.95
        reason = "background runtime agent is not installed or not running"
        blockers.append("background agent unavailable")
    elif runtime_agent_running and not runtime_loop_enabled:
        call = "enable_runtime_loop"
        mode = "safe"
        priority = 80
        confidence = 0.94
        reason = "runtime loop is off while the background agent is active"
        blockers.append("runtime loop disabled")
    elif recovery_observed and not recovery_ready:
        call = "stabilize_recovery"
        mode = "safe"
        priority = 78
        confidence = 0.93
        reason = "trusted compatible recovery baseline is required before mutation"
        if recovery_snapshot_count <= 0:
            blockers.append("no recovery snapshots available")
        if recovery_compatible_count <= 0:
            blockers.append("latest compatible snapshot missing")
    elif requested_code_mutation and (not code_scope_ready or code_out_of_scope_count > 0 or code_dirty_in_scope_count > 0):
        call = "wait_for_clean_scope"
        mode = "safe"
        priority = 77
        confidence = 0.91
        reason = "code mutation targets are not cleanly inside the writable workbench scope"
        if not code_scope_ready:
            blockers.append("code scope not ready")
        if code_out_of_scope_count > 0:
            blockers.append(f"{code_out_of_scope_count} code target(s) out of scope")
        if code_dirty_in_scope_count > 0:
            blockers.append(f"{code_dirty_in_scope_count} in-scope code target(s) already dirty")
    elif requested_code_mutation and not code_verification_surface_ready:
        call = "run_code_canary"
        mode = "guarded"
        priority = 76
        confidence = 0.86 if code_source_canary_ready else 0.78
        reason = "code mutation lacks focused compile/test coverage, so bounded canary verification should run first"
        blockers.append("focused code verification surface missing")
        if not code_source_canary_ready:
            blockers.append("source canary not yet warmed")
    elif requested_code_mutation and code_scope_ready and code_verification_ready:
        call = "run_code_fix_loop"
        mode = "guarded"
        priority = 75
        confidence = 0.87
        reason = "code mutation is ready for bounded fix-and-verify execution"
    elif current_goal_requires_user or current_goal_state == "blocked":
        call = "wait_for_user"
        mode = "blocked"
        priority = 74
        confidence = 0.9
        reason = "an active goal is blocked and needs user review or blocker clearance"
        if current_goal_title:
            blockers.append(f"goal blocked: {current_goal_title}")
    elif current_goal_title and open_goal_count > 0 and causal_action_bias == "goal_progress":
        call = "goal_progress"
        mode = "normal"
        priority = 64 if goal_loop_due_now else 58
        confidence = 0.82
        reason = "the world model has an active goal and the system is stable enough for bounded progress"
    elif revalidation_ready_count > 0 and pressure_ready and same_system and not has_contradiction:
        call = "self_derivation_revalidate"
        mode = "guarded"
        priority = 77
        confidence = 0.88
        reason = "strategy memory is ready for bounded revalidation under stable conditions"
    elif jobs_pending > 0:
        call = "jobs_tick"
        mode = "normal"
        priority = 75
        confidence = 0.9
        reason = "assistant queue has pending jobs"
    elif (
        bool(evolution.get("self_evolution_ready", False))
        and bool(evolution.get("due_now", False))
        and bool(evolution.get("candidate_available", False))
        and bool(evolution.get("beneficial", False))
        and str(evolution.get("recommended_action", "observe")) in {"auto_run", "promote"}
    ):
        call = "evolution_auto_run"
        mode = "guarded"
        priority = 70
        confidence = 0.86
        reason = "bounded self evolution is ready and predicted to help"
    elif (
        bool(source_evolution.get("source_evolution_ready", False))
        and bool(source_evolution.get("due_now", False))
        and bool(source_evolution.get("candidate_available", False))
        and bool(source_evolution.get("beneficial", False))
        and str(source_evolution.get("recommended_action", "observe")) in {"auto_run", "promote"}
    ):
        call = "source_evolution_auto_run"
        mode = "guarded"
        priority = 65
        confidence = 0.84
        reason = "source evolution is ready and bounded promotion is available"
    return {
        "ok": True,
        "time_utc": _utc_now(),
        "call": call,
        "mode": mode,
        "priority": priority,
        "confidence": round(confidence, 2),
        "reason": reason,
        "blocking_factors": blockers,
        "observed": {
            "runtime_ready": runtime_ready,
            "runtime_missing": runtime_missing,
            "same_system": same_system,
            "has_contradiction": has_contradiction,
            "approvals_pending": approvals_pending,
            "jobs_pending": jobs_pending,
            "pressure_ready": pressure_ready,
            "recovery_observed": recovery_observed,
            "recovery_ready": recovery_ready,
            "recovery_snapshot_count": recovery_snapshot_count,
            "recovery_compatible_count": recovery_compatible_count,
            "revalidation_ready_count": revalidation_ready_count,
            "requested_code_mutation": requested_code_mutation,
            "code_scope_ready": code_scope_ready,
            "code_verification_ready": code_verification_ready,
            "code_verification_surface_ready": code_verification_surface_ready,
            "code_dirty_worktree": code_dirty_worktree,
            "code_dirty_in_scope_count": code_dirty_in_scope_count,
            "code_source_canary_ready": code_source_canary_ready,
            "goal_count": goal_count,
            "open_goal_count": open_goal_count,
            "blocked_goal_count": blocked_goal_count,
            "current_goal_title": current_goal_title,
            "goal_loop_due_now": goal_loop_due_now,
            "observation_blocking_event_count": observation_blocking_event_count,
            "causal_action_bias": causal_action_bias,
        },
    }


def governor_status(cwd: str, *, world_model: dict[str, Any] | None = None) -> dict[str, Any]:
    return governor_decide(cwd, world_model=world_model)
