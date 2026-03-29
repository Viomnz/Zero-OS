from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

from zero_os.goal_memory import goal_memory_status
from zero_os.observation_bus import emit_observation, observation_stream_status, observation_summary
from zero_os.state_registry import boot_state_registry, get_state_store, update_state_store

WORLD_MODEL_SCHEMA_VERSION = 4
_DOMAIN_FRESHNESS_TTL_SECONDS = {
    "runtime": 30,
    "continuity": 30,
    "pressure": 90,
    "recovery": 180,
    "approvals": 20,
    "jobs": 20,
    "self_derivation": 120,
    "evolution": 180,
    "source_evolution": 180,
    "control_workflows": 90,
    "capability_control_map": 90,
    "zero_engine": 45,
    "codebase": 45,
    "goals": 60,
    "observation_stream": 20,
}
_CRITICAL_STALE_DOMAINS = {"runtime", "continuity", "approvals", "jobs", "recovery", "codebase", "goals"}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_utc(value: Any) -> datetime | None:
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


def _age_seconds(observed_at_utc: Any) -> float | None:
    observed = _parse_utc(observed_at_utc)
    if observed is None:
        return None
    return max(0.0, round((datetime.now(timezone.utc) - observed).total_seconds(), 3))


def _source_observed_at(payload: Any, fallback_utc: str) -> str:
    if not isinstance(payload, dict):
        return str(fallback_utc)
    for key in ("time_utc", "generated_utc", "updated_utc", "last_checked_utc", "last_run_utc", "decided_utc"):
        candidate = str(payload.get(key, "") or "").strip()
        if candidate:
            return candidate
    return str(fallback_utc)


def _as_bool(value: Any) -> bool:
    return bool(value)


def _as_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _as_float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _domain(
    *,
    name: str,
    source: str,
    healthy: bool,
    blocking: bool,
    confidence: float,
    summary: dict[str, Any],
    observed_at_utc: str,
    freshness_ttl_seconds: int,
) -> dict[str, Any]:
    age_seconds = _age_seconds(observed_at_utc)
    stale = age_seconds is None or age_seconds > max(1, int(freshness_ttl_seconds))
    return {
        "name": str(name),
        "source": str(source),
        "healthy": bool(healthy),
        "blocking": bool(blocking),
        "confidence": max(0.0, min(1.0, float(confidence))),
        "summary": deepcopy(summary),
        "observed_at_utc": str(observed_at_utc or ""),
        "freshness_ttl_seconds": max(1, int(freshness_ttl_seconds)),
        "age_seconds": age_seconds,
        "stale": stale,
    }


def _apply_world_model_freshness(payload: dict[str, Any]) -> dict[str, Any]:
    model = deepcopy(dict(payload or {}))
    domains = dict(model.get("domains") or {})
    stale_domains: list[str] = []
    blocked_domains = set(str(item) for item in list(model.get("blocked_domains", [])) if str(item))
    degraded_domains = set(str(item) for item in list(model.get("degraded_domains", [])) if str(item))
    for name, raw_domain in domains.items():
        domain = dict(raw_domain or {})
        observed_at_utc = str(domain.get("observed_at_utc", "") or model.get("time_utc", ""))
        freshness_ttl_seconds = max(1, int(domain.get("freshness_ttl_seconds", _DOMAIN_FRESHNESS_TTL_SECONDS.get(str(name), 60)) or 60))
        age_seconds = _age_seconds(observed_at_utc)
        stale = age_seconds is None or age_seconds > freshness_ttl_seconds
        domain["observed_at_utc"] = observed_at_utc
        domain["freshness_ttl_seconds"] = freshness_ttl_seconds
        domain["age_seconds"] = age_seconds
        domain["stale"] = stale
        domains[str(name)] = domain
        if stale:
            stale_domains.append(str(name))
            degraded_domains.add(str(name))
            if str(name) in _CRITICAL_STALE_DOMAINS:
                blocked_domains.add(str(name))
    model["domains"] = domains
    model["stale_domains"] = sorted(stale_domains)
    model["stale"] = bool(stale_domains)
    model["fresh_enough"] = not any(name in _CRITICAL_STALE_DOMAINS for name in stale_domains)
    model["blocked_domains"] = sorted(blocked_domains)
    model["degraded_domains"] = sorted(degraded_domains)
    model["blocking_domain_count"] = len(model["blocked_domains"])
    model["degraded_domain_count"] = len(model["degraded_domains"])
    if model["stale"] and not model["fresh_enough"]:
        model["ok"] = False
        model["stale_reason"] = "critical domains stale"
        model["hint"] = "run: zero ai runtime run"
    return model


def _build_causal_assessment(
    blocked_domains: list[str],
    degraded_domains: list[str],
    goal_memory: dict[str, Any],
    observation_stream: dict[str, Any],
) -> dict[str, Any]:
    blocked = [str(item) for item in list(blocked_domains) if str(item)]
    degraded = [str(item) for item in list(degraded_domains) if str(item)]
    current_goal_title = str(goal_memory.get("current_goal_title", "") or "")
    current_goal_next_action = str(goal_memory.get("current_goal_next_action", "") or "")
    current_goal_blocked = bool(goal_memory.get("current_goal_requires_user", False)) or str(goal_memory.get("current_goal_state", "")) == "blocked"
    recent = [dict(item or {}) for item in list(observation_stream.get("recent", [])) if isinstance(item, dict)]
    recent_blocking = [item for item in recent if bool(item.get("blocking", False))]

    action_bias = "observe"
    primary_cause = "system_stable"
    if "approvals" in blocked or current_goal_blocked:
        action_bias = "wait_for_user"
        primary_cause = "approval_or_goal_block"
    elif "continuity" in blocked:
        action_bias = "repair_continuity"
        primary_cause = "continuity_unstable"
    elif "runtime" in blocked:
        action_bias = "run_runtime"
        primary_cause = "runtime_not_ready"
    elif "recovery" in blocked:
        action_bias = "stabilize_recovery"
        primary_cause = "recovery_not_trusted"
    elif "codebase" in blocked:
        action_bias = "wait_for_clean_scope"
        primary_cause = "codebase_not_clean"
    elif current_goal_title:
        action_bias = "goal_progress"
        primary_cause = "goal_ready_for_progress"

    predicted_failure_modes: list[str] = []
    if "runtime" in blocked:
        predicted_failure_modes.append("runtime_actions_may_use_stale_truth")
    if "continuity" in blocked:
        predicted_failure_modes.append("autonomous_mutation_may_conflict_with_system_state")
    if "recovery" in blocked:
        predicted_failure_modes.append("rollback_baseline_missing_for_mutation")
    if "codebase" in blocked:
        predicted_failure_modes.append("code_changes_may_collide_with_dirty_scope")
    if current_goal_blocked:
        predicted_failure_modes.append("goal_progress_waiting_for_human_or_blocker_clearance")

    blocking_chain = blocked[:]
    if current_goal_blocked and "goals" not in blocking_chain:
        blocking_chain.append("goals")

    return {
        "primary_cause": primary_cause,
        "action_bias": action_bias,
        "blocking_chain": blocking_chain,
        "degraded_chain": degraded,
        "predicted_failure_modes": predicted_failure_modes,
        "ready_for_goal_execution": bool(current_goal_title) and not blocked and not current_goal_blocked,
        "current_goal_title": current_goal_title,
        "current_goal_next_action": current_goal_next_action,
        "recent_blocking_event_count": len(recent_blocking),
        "recent_blocking_domains": sorted({str(item.get("domain", "")) for item in recent_blocking if str(item.get("domain", ""))}),
    }


def build_world_model(cwd: str, *, sources: dict[str, Any] | None = None) -> dict[str, Any]:
    generated_utc = _utc_now()
    raw_sources = dict(sources or {})
    runtime = dict(raw_sources.get("runtime") or {})
    runtime_loop = dict(raw_sources.get("runtime_loop") or runtime.get("runtime_loop") or {})
    runtime_agent = dict(raw_sources.get("runtime_agent") or runtime.get("runtime_agent") or {})
    continuity = dict(raw_sources.get("continuity") or {})
    continuity_block = dict(continuity.get("continuity") or raw_sources.get("continuity_block") or {})
    contradiction_block = dict(continuity.get("contradiction_detection") or raw_sources.get("contradiction") or {})
    pressure = dict(raw_sources.get("pressure") or {})
    control_workflows = dict(raw_sources.get("control_workflows") or {})
    capability_map = dict(raw_sources.get("capability_control_map") or raw_sources.get("capability_map") or {})
    zero_engine = dict(raw_sources.get("zero_engine") or {})
    zero_engine_subsystems = dict(zero_engine.get("subsystems") or {})
    zero_engine_recovery = dict((zero_engine_subsystems.get("recovery") or {}).get("facts") or {})
    recovery = dict(raw_sources.get("recovery") or zero_engine_recovery)
    self_derivation = dict(raw_sources.get("self_derivation") or {})
    evolution = dict(raw_sources.get("evolution") or {})
    source_evolution = dict(raw_sources.get("source_evolution") or {})
    code_workbench = dict(raw_sources.get("code_workbench") or {})
    approvals = dict(raw_sources.get("approvals") or {})
    jobs = dict(raw_sources.get("jobs") or {})
    goals = dict(raw_sources.get("goal_memory") or goal_memory_status(cwd) or {})
    observation_stream = dict(raw_sources.get("observation_stream") or observation_stream_status(cwd) or {})

    runtime_ready = _as_bool(runtime.get("runtime_ready", False))
    runtime_missing = _as_bool(runtime.get("missing", False))
    runtime_score = _as_float(runtime.get("runtime_score", 0.0))
    runtime_loop_enabled = _as_bool(runtime_loop.get("enabled", False))
    runtime_agent_installed = _as_bool(runtime_agent.get("installed", False))
    runtime_agent_running = _as_bool(runtime_agent.get("running", False))

    continuity_score = _as_float(continuity_block.get("continuity_score", 0.0))
    same_system = _as_bool(continuity_block.get("same_system", False))
    has_contradiction = _as_bool(contradiction_block.get("has_contradiction", False))
    continuity_healthy = same_system and not has_contradiction

    pressure_missing = _as_bool(pressure.get("missing", False))
    pressure_score = _as_float(pressure.get("overall_score", 0.0))
    pressure_ready = (not pressure_missing) and pressure_score >= 100.0

    recovery_observed = bool(recovery) or bool(zero_engine_recovery)
    recovery_snapshot_count = _as_int(recovery.get("snapshot_count", 0))
    recovery_compatible_count = _as_int(recovery.get("compatible_count", 0))
    recovery_latest_compatible = str(recovery.get("latest_compatible_snapshot_id", "") or "")
    recovery_ready = (recovery_compatible_count > 0 and bool(recovery_latest_compatible)) if recovery_observed else True

    approvals_pending = _as_int(approvals.get("pending_count", approvals.get("count", 0)))
    approvals_expired = _as_int(approvals.get("expired_count", 0))
    jobs_pending = _as_int(jobs.get("count", 0))
    revalidation_ready_count = _as_int(self_derivation.get("revalidation_ready_count", 0))
    goal_count = _as_int(goals.get("goal_count", 0))
    open_goal_count = _as_int(goals.get("open_count", 0))
    blocked_goal_count = _as_int(goals.get("blocked_count", 0))
    resolved_goal_count = _as_int(goals.get("resolved_count", 0))
    current_goal_title = str(goals.get("current_goal_title", "") or "")
    current_goal_next_action = str(goals.get("current_goal_next_action", "") or "")
    current_goal_requires_user = _as_bool(goals.get("current_goal_requires_user", False))
    current_goal_state = str(goals.get("current_goal_state", "") or "")
    current_goal_risk = str(goals.get("current_goal_risk", "low") or "low")
    goal_loop_enabled = _as_bool(goals.get("loop_enabled", False))
    goal_loop_due_now = _as_bool(goals.get("loop_due_now", False))
    observation_event_count = _as_int(observation_stream.get("event_count", 0))
    observation_blocking_event_count = _as_int(observation_stream.get("blocking_event_count", 0))
    observation_warning_event_count = _as_int(observation_stream.get("warning_event_count", 0))
    observation_error_event_count = _as_int(observation_stream.get("error_event_count", 0))

    evolution_ready = _as_bool(evolution.get("self_evolution_ready", False))
    evolution_due = _as_bool(evolution.get("due_now", False))
    evolution_candidate = _as_bool((evolution.get("proposal") or {}).get("candidate_available", False))
    evolution_beneficial = _as_bool((evolution.get("proposal") or {}).get("beneficial", False))

    source_evolution_ready = _as_bool(source_evolution.get("source_evolution_ready", False))
    source_evolution_due = _as_bool(source_evolution.get("due_now", False))
    source_evolution_candidate = _as_bool((source_evolution.get("proposal") or {}).get("candidate_available", False))
    source_evolution_beneficial = _as_bool((source_evolution.get("proposal") or {}).get("beneficial", False))
    code_workbench_observed = bool(code_workbench)
    code_workspace_ready = _as_bool(code_workbench.get("workspace_ready", False))
    code_requested_mutation = _as_bool(code_workbench.get("requested_code_mutation", False))
    code_scope_ready = _as_bool(code_workbench.get("scope_ready", False))
    code_verification_ready = _as_bool(code_workbench.get("verification_ready", False))
    code_verification_surface_ready = _as_bool(code_workbench.get("verification_surface_ready", False))
    code_strong_verification_ready = _as_bool(code_workbench.get("strong_verification_ready", False))
    code_target_file_count = _as_int(code_workbench.get("target_file_count", 0))
    code_in_scope_count = _as_int(code_workbench.get("in_scope_count", 0))
    code_out_of_scope_count = _as_int(code_workbench.get("out_of_scope_count", 0))
    code_missing_in_scope_count = _as_int(code_workbench.get("missing_in_scope_count", 0))
    code_git_available = _as_bool(code_workbench.get("git_available", False))
    code_dirty_worktree = _as_bool(code_workbench.get("dirty_worktree", False))
    code_git_change_count = _as_int(code_workbench.get("git_change_count", 0))
    code_dirty_in_scope_count = _as_int(code_workbench.get("dirty_in_scope_count", 0))
    code_focused_test_count = _as_int(code_workbench.get("focused_test_count", 0))
    code_compile_target_count = _as_int(code_workbench.get("compile_target_count", 0))
    code_source_canary_ready = _as_bool(code_workbench.get("source_canary_ready", False))
    code_source_last_canary_passed = _as_bool(code_workbench.get("source_last_canary_passed", False))
    code_source_pending_candidate = _as_bool(code_workbench.get("source_pending_candidate", False))
    code_ready = _as_bool(code_workbench.get("ready", False)) if code_workbench_observed else True

    observations = [
        emit_observation(
            domain="runtime",
            name="runtime_ready",
            value=runtime_ready,
            source="runtime",
            confidence=1.0,
            blocking=runtime_missing or not runtime_ready,
            severity="error" if runtime_missing else ("warning" if not runtime_ready else "info"),
            affects=["autonomy", "execution"],
            details={"runtime_score": runtime_score, "missing": runtime_missing},
        ),
        emit_observation(
            domain="runtime",
            name="runtime_agent_running",
            value=runtime_agent_running,
            source="runtime_agent",
            confidence=1.0,
            blocking=runtime_agent_installed and not runtime_agent_running,
            severity="warning" if runtime_agent_installed and not runtime_agent_running else "info",
            affects=["background_runtime"],
            details={"installed": runtime_agent_installed},
        ),
        emit_observation(
            domain="runtime",
            name="runtime_loop_enabled",
            value=runtime_loop_enabled,
            source="runtime_loop",
            confidence=1.0,
            blocking=False,
            severity="warning" if runtime_agent_running and not runtime_loop_enabled else "info",
            depends_on=["runtime_agent_running"],
            affects=["background_runtime"],
        ),
        emit_observation(
            domain="continuity",
            name="continuity_healthy",
            value=continuity_healthy,
            source="self_continuity",
            confidence=1.0,
            blocking=not continuity_healthy,
            severity="error" if has_contradiction else ("warning" if not same_system else "info"),
            affects=["autonomy", "self_repair", "runtime"],
            details={"continuity_score": continuity_score, "has_contradiction": has_contradiction},
        ),
        emit_observation(
            domain="pressure",
            name="pressure_ready",
            value=pressure_ready,
            source="pressure_harness",
            confidence=0.95,
            blocking=False,
            severity="warning" if not pressure_ready else "info",
            affects=["self_derivation", "maintenance"],
            details={"overall_score": pressure_score, "missing": pressure_missing},
        ),
        emit_observation(
            domain="recovery",
            name="compatible_snapshot_ready",
            value=recovery_ready,
            source="recovery",
            confidence=0.97,
            blocking=recovery_observed and not recovery_ready,
            severity="info" if not recovery_observed else ("warning" if recovery_snapshot_count > 0 and not recovery_ready else ("error" if recovery_snapshot_count <= 0 else "info")),
            affects=["recover", "self_repair", "mutation"],
            details={
                "observed": recovery_observed,
                "snapshot_count": recovery_snapshot_count,
                "compatible_count": recovery_compatible_count,
                "latest_compatible_snapshot_id": recovery_latest_compatible,
            },
        ),
        emit_observation(
            domain="approvals",
            name="approvals_pending",
            value=approvals_pending,
            source="approval_workflow",
            confidence=1.0,
            blocking=approvals_pending > 0,
            severity="warning" if approvals_pending > 0 else "info",
            affects=["autonomy", "mutation"],
            details={"expired_count": approvals_expired},
        ),
        emit_observation(
            domain="jobs",
            name="jobs_pending",
            value=jobs_pending,
            source="assistant_job_runner",
            confidence=1.0,
            blocking=False,
            severity="warning" if jobs_pending > 0 else "info",
            affects=["runtime_queue"],
        ),
        emit_observation(
            domain="goals",
            name="current_goal_present",
            value=bool(current_goal_title),
            source="goal_memory",
            confidence=0.9,
            blocking=False,
            severity="warning" if current_goal_title else "info",
            affects=["goal_progress"],
            details={
                "goal_count": goal_count,
                "open_count": open_goal_count,
                "current_goal_title": current_goal_title,
                "current_goal_next_action": current_goal_next_action,
            },
        ),
        emit_observation(
            domain="goals",
            name="current_goal_blocked",
            value=current_goal_requires_user or current_goal_state == "blocked",
            source="goal_memory",
            confidence=0.92,
            blocking=current_goal_requires_user or current_goal_state == "blocked",
            severity="warning" if current_goal_requires_user or current_goal_state == "blocked" else "info",
            affects=["goal_progress", "autonomy"],
            details={
                "current_goal_title": current_goal_title,
                "current_goal_state": current_goal_state,
                "blocked_count": blocked_goal_count,
            },
        ),
        emit_observation(
            domain="observation_stream",
            name="recent_blocking_events_present",
            value=observation_blocking_event_count > 0,
            source="observation_stream",
            confidence=0.85,
            blocking=False,
            severity="warning" if observation_blocking_event_count > 0 else "info",
            affects=["attention", "goal_progress"],
            details={
                "event_count": observation_event_count,
                "blocking_event_count": observation_blocking_event_count,
                "warning_event_count": observation_warning_event_count,
                "error_event_count": observation_error_event_count,
            },
        ),
        emit_observation(
            domain="self_derivation",
            name="revalidation_ready_count",
            value=revalidation_ready_count,
            source="self_derivation",
            confidence=0.9,
            blocking=False,
            severity="warning" if revalidation_ready_count > 0 else "info",
            depends_on=["pressure_ready", "continuity_healthy"],
            affects=["strategy_memory"],
        ),
        emit_observation(
            domain="evolution",
            name="bounded_self_evolution_ready",
            value=evolution_ready and evolution_due and evolution_candidate and evolution_beneficial,
            source="zero_ai_evolution",
            confidence=0.9,
            blocking=False,
            severity="info",
            affects=["self_evolution"],
        ),
        emit_observation(
            domain="source_evolution",
            name="source_evolution_ready",
            value=source_evolution_ready and source_evolution_due and source_evolution_candidate and source_evolution_beneficial,
            source="zero_ai_source_evolution",
            confidence=0.9,
            blocking=False,
            severity="info",
            affects=["source_evolution"],
        ),
    ]
    if code_workbench_observed:
        observations.append(
            emit_observation(
                domain="codebase",
                name="code_workbench_ready",
                value=code_ready,
                source="code_workbench",
                confidence=0.9,
                blocking=code_requested_mutation and (not code_scope_ready or code_out_of_scope_count > 0 or code_dirty_in_scope_count > 0),
                severity="warning" if code_requested_mutation and (not code_scope_ready or code_out_of_scope_count > 0 or code_dirty_in_scope_count > 0) else "info",
                affects=["code_mutation", "verification"],
                details={
                    "requested_code_mutation": code_requested_mutation,
                    "scope_ready": code_scope_ready,
                    "verification_ready": code_verification_ready,
                    "verification_surface_ready": code_verification_surface_ready,
                    "strong_verification_ready": code_strong_verification_ready,
                    "target_file_count": code_target_file_count,
                    "in_scope_count": code_in_scope_count,
                    "out_of_scope_count": code_out_of_scope_count,
                    "missing_in_scope_count": code_missing_in_scope_count,
                    "git_available": code_git_available,
                    "dirty_worktree": code_dirty_worktree,
                    "dirty_in_scope_count": code_dirty_in_scope_count,
                    "source_canary_ready": code_source_canary_ready,
                },
            )
        )
        observations.append(
            emit_observation(
                domain="codebase",
                name="code_scope_clean",
                value=code_dirty_in_scope_count == 0,
                source="code_workbench",
                confidence=0.88,
                blocking=code_requested_mutation and code_dirty_in_scope_count > 0,
                severity="warning" if code_requested_mutation and code_dirty_in_scope_count > 0 else "info",
                affects=["code_mutation"],
                details={"dirty_in_scope_count": code_dirty_in_scope_count},
            )
        )
        observations.append(
            emit_observation(
                domain="codebase",
                name="code_verification_surface_ready",
                value=code_verification_surface_ready,
                source="code_workbench",
                confidence=0.87,
                blocking=False,
                severity="warning" if code_requested_mutation and not code_verification_surface_ready else "info",
                affects=["code_verification", "code_mutation"],
                details={
                    "focused_test_count": code_focused_test_count,
                    "compile_target_count": code_compile_target_count,
                    "strong_verification_ready": code_strong_verification_ready,
                },
            )
        )
        observations.append(
            emit_observation(
                domain="codebase",
                name="code_canary_ready",
                value=code_source_canary_ready,
                source="code_workbench",
                confidence=0.86,
                blocking=False,
                severity="info",
                affects=["code_canary"],
                details={
                    "source_last_canary_passed": code_source_last_canary_passed,
                    "source_pending_candidate": code_source_pending_candidate,
                },
            )
        )

    domains = {
        "runtime": _domain(
            name="runtime",
            source="phase_runtime",
            healthy=runtime_ready and not runtime_missing,
            blocking=runtime_missing or not runtime_ready,
            confidence=1.0,
            observed_at_utc=_source_observed_at(runtime, generated_utc),
            freshness_ttl_seconds=_DOMAIN_FRESHNESS_TTL_SECONDS["runtime"],
            summary={
                "runtime_ready": runtime_ready,
                "runtime_missing": runtime_missing,
                "runtime_score": runtime_score,
                "runtime_loop_enabled": runtime_loop_enabled,
                "runtime_agent_installed": runtime_agent_installed,
                "runtime_agent_running": runtime_agent_running,
            },
        ),
        "continuity": _domain(
            name="continuity",
            source="self_continuity",
            healthy=continuity_healthy,
            blocking=not continuity_healthy,
            confidence=1.0,
            observed_at_utc=_source_observed_at(continuity, generated_utc),
            freshness_ttl_seconds=_DOMAIN_FRESHNESS_TTL_SECONDS["continuity"],
            summary={
                "same_system": same_system,
                "has_contradiction": has_contradiction,
                "continuity_score": continuity_score,
            },
        ),
        "pressure": _domain(
            name="pressure",
            source="pressure_harness",
            healthy=pressure_ready,
            blocking=False,
            confidence=0.95,
            observed_at_utc=_source_observed_at(pressure, generated_utc),
            freshness_ttl_seconds=_DOMAIN_FRESHNESS_TTL_SECONDS["pressure"],
            summary={"pressure_ready": pressure_ready, "overall_score": pressure_score, "missing": pressure_missing},
        ),
        "recovery": _domain(
            name="recovery",
            source="recovery",
            healthy=recovery_ready,
            blocking=recovery_observed and not recovery_ready,
            confidence=0.97,
            observed_at_utc=_source_observed_at(recovery, generated_utc),
            freshness_ttl_seconds=_DOMAIN_FRESHNESS_TTL_SECONDS["recovery"],
            summary={
                "observed": recovery_observed,
                "snapshot_count": recovery_snapshot_count,
                "compatible_count": recovery_compatible_count,
                "latest_compatible_snapshot_id": recovery_latest_compatible,
                "compatible_snapshot_ready": recovery_ready,
            },
        ),
        "approvals": _domain(
            name="approvals",
            source="approval_workflow",
            healthy=approvals_pending == 0,
            blocking=approvals_pending > 0,
            confidence=1.0,
            observed_at_utc=_source_observed_at(approvals, generated_utc),
            freshness_ttl_seconds=_DOMAIN_FRESHNESS_TTL_SECONDS["approvals"],
            summary={"pending_count": approvals_pending, "expired_count": approvals_expired},
        ),
        "jobs": _domain(
            name="jobs",
            source="assistant_job_runner",
            healthy=jobs_pending == 0,
            blocking=False,
            confidence=1.0,
            observed_at_utc=_source_observed_at(jobs, generated_utc),
            freshness_ttl_seconds=_DOMAIN_FRESHNESS_TTL_SECONDS["jobs"],
            summary={"pending_count": jobs_pending},
        ),
        "self_derivation": _domain(
            name="self_derivation",
            source="self_derivation_engine",
            healthy=_as_bool(self_derivation.get("ok", False)),
            blocking=False,
            confidence=0.9,
            observed_at_utc=_source_observed_at(self_derivation, generated_utc),
            freshness_ttl_seconds=_DOMAIN_FRESHNESS_TTL_SECONDS["self_derivation"],
            summary={
                "ok": _as_bool(self_derivation.get("ok", False)),
                "revalidation_ready_count": revalidation_ready_count,
                "strategy_outcome_count": _as_int(self_derivation.get("strategy_outcome_count", 0)),
                "quarantined_strategy_count": _as_int(self_derivation.get("quarantined_strategy_count", 0)),
            },
        ),
        "evolution": _domain(
            name="evolution",
            source="zero_ai_evolution",
            healthy=_as_bool(evolution.get("ok", False)),
            blocking=False,
            confidence=0.9,
            observed_at_utc=_source_observed_at(evolution, generated_utc),
            freshness_ttl_seconds=_DOMAIN_FRESHNESS_TTL_SECONDS["evolution"],
            summary={
                "self_evolution_ready": evolution_ready,
                "due_now": evolution_due,
                "candidate_available": evolution_candidate,
                "beneficial": evolution_beneficial,
                "recommended_action": str(evolution.get("recommended_action", "observe") or "observe"),
            },
        ),
        "source_evolution": _domain(
            name="source_evolution",
            source="zero_ai_source_evolution",
            healthy=_as_bool(source_evolution.get("ok", False)),
            blocking=False,
            confidence=0.9,
            observed_at_utc=_source_observed_at(source_evolution, generated_utc),
            freshness_ttl_seconds=_DOMAIN_FRESHNESS_TTL_SECONDS["source_evolution"],
            summary={
                "source_evolution_ready": source_evolution_ready,
                "due_now": source_evolution_due,
                "candidate_available": source_evolution_candidate,
                "beneficial": source_evolution_beneficial,
                "recommended_action": str(source_evolution.get("recommended_action", "observe") or "observe"),
            },
        ),
        "control_workflows": _domain(
            name="control_workflows",
            source="zero_ai_control_workflows",
            healthy=_as_bool(control_workflows.get("ok", False)),
            blocking=False,
            confidence=0.85,
            observed_at_utc=_source_observed_at(control_workflows, generated_utc),
            freshness_ttl_seconds=_DOMAIN_FRESHNESS_TTL_SECONDS["control_workflows"],
            summary={
                "ok": _as_bool(control_workflows.get("ok", False)),
                "ready_workflow_count": _as_int(control_workflows.get("workflow_count", 0)),
            },
        ),
        "capability_control_map": _domain(
            name="capability_control_map",
            source="zero_ai_capability_map",
            healthy=_as_bool(capability_map.get("ok", False)),
            blocking=False,
            confidence=0.85,
            observed_at_utc=_source_observed_at(capability_map, generated_utc),
            freshness_ttl_seconds=_DOMAIN_FRESHNESS_TTL_SECONDS["capability_control_map"],
            summary={
                "ok": _as_bool(capability_map.get("ok", False)),
                "fully_autonomous_control": _as_bool(capability_map.get("fully_autonomous_control", False)),
                "overall_score": _as_float(capability_map.get("overall_score", 0.0)),
            },
        ),
        "zero_engine": _domain(
            name="zero_engine",
            source="zero_engine",
            healthy=_as_bool(zero_engine.get("ok", False)),
            blocking=False,
            confidence=0.9,
            observed_at_utc=_source_observed_at(zero_engine, generated_utc),
            freshness_ttl_seconds=_DOMAIN_FRESHNESS_TTL_SECONDS["zero_engine"],
            summary={
                "ok": _as_bool(zero_engine.get("ok", False)),
                "subsystem_count": _as_int(zero_engine.get("subsystem_count", zero_engine.get("adapter_count", 0))),
            },
        ),
        "goals": _domain(
            name="goals",
            source="goal_memory",
            healthy=not current_goal_requires_user and blocked_goal_count == 0,
            blocking=current_goal_requires_user or current_goal_state == "blocked",
            confidence=0.9,
            observed_at_utc=_source_observed_at(goals, generated_utc),
            freshness_ttl_seconds=_DOMAIN_FRESHNESS_TTL_SECONDS["goals"],
            summary={
                "goal_count": goal_count,
                "open_count": open_goal_count,
                "blocked_count": blocked_goal_count,
                "resolved_count": resolved_goal_count,
                "current_goal_title": current_goal_title,
                "current_goal_next_action": current_goal_next_action,
                "current_goal_requires_user": current_goal_requires_user,
                "current_goal_state": current_goal_state,
                "current_goal_risk": current_goal_risk,
                "loop_enabled": goal_loop_enabled,
                "loop_due_now": goal_loop_due_now,
            },
        ),
        "observation_stream": _domain(
            name="observation_stream",
            source="observation_bus",
            healthy=observation_error_event_count == 0,
            blocking=False,
            confidence=0.84,
            observed_at_utc=_source_observed_at(observation_stream, generated_utc),
            freshness_ttl_seconds=_DOMAIN_FRESHNESS_TTL_SECONDS["observation_stream"],
            summary={
                "event_count": observation_event_count,
                "blocking_event_count": observation_blocking_event_count,
                "warning_event_count": observation_warning_event_count,
                "error_event_count": observation_error_event_count,
                "domains": list(observation_stream.get("domains", [])),
            },
        ),
    }
    if code_workbench_observed:
        domains["codebase"] = _domain(
            name="codebase",
            source="code_workbench",
            healthy=code_ready and code_dirty_in_scope_count == 0,
            blocking=code_requested_mutation and (not code_scope_ready or code_out_of_scope_count > 0 or code_dirty_in_scope_count > 0),
            confidence=0.9,
            observed_at_utc=_source_observed_at(code_workbench, generated_utc),
            freshness_ttl_seconds=_DOMAIN_FRESHNESS_TTL_SECONDS["codebase"],
            summary={
                "workspace_ready": code_workspace_ready,
                "requested_code_mutation": code_requested_mutation,
                "scope_ready": code_scope_ready,
                "verification_ready": code_verification_ready,
                "verification_surface_ready": code_verification_surface_ready,
                "strong_verification_ready": code_strong_verification_ready,
                "target_file_count": code_target_file_count,
                "in_scope_count": code_in_scope_count,
                "out_of_scope_count": code_out_of_scope_count,
                "missing_in_scope_count": code_missing_in_scope_count,
                "git_available": code_git_available,
                "dirty_worktree": code_dirty_worktree,
                "git_change_count": code_git_change_count,
                "dirty_in_scope_count": code_dirty_in_scope_count,
                "focused_test_count": code_focused_test_count,
                "compile_target_count": code_compile_target_count,
                "source_canary_ready": code_source_canary_ready,
                "source_last_canary_passed": code_source_last_canary_passed,
                "source_pending_candidate": code_source_pending_candidate,
            },
        )

    blocked_domains = sorted([name for name, domain in domains.items() if bool(domain.get("blocking", False))])
    degraded_domains = sorted([name for name, domain in domains.items() if not bool(domain.get("healthy", False))])
    summary = observation_summary(observations)
    causal_assessment = _build_causal_assessment(blocked_domains, degraded_domains, goals, observation_stream)
    return _apply_world_model_freshness(
        {
        "ok": True,
        "schema_version": WORLD_MODEL_SCHEMA_VERSION,
        "time_utc": generated_utc,
        "cwd": str(cwd),
        "domain_count": len(domains),
        "fact_count": len(observations),
        "blocking_domain_count": len(blocked_domains),
        "degraded_domain_count": len(degraded_domains),
        "blocked_domains": blocked_domains,
        "degraded_domains": degraded_domains,
        "observation_summary": summary,
        "causal_assessment": causal_assessment,
        "attention": {
            "current_goal_title": current_goal_title,
            "recent_blocking_event_count": observation_blocking_event_count,
            "action_bias": str(causal_assessment.get("action_bias", "observe")),
        },
        "domains": domains,
        "facts": observations,
        }
    )


def persist_world_model(cwd: str, world_model: dict[str, Any], *, flush: bool = False) -> dict[str, Any]:
    boot_state_registry(cwd, names=["world_model_latest"])
    return update_state_store(cwd, "world_model_latest", lambda current: deepcopy(world_model), flush=flush)


def world_model_status(cwd: str) -> dict[str, Any]:
    boot_state_registry(cwd, names=["world_model_latest"])
    payload = dict(get_state_store(cwd, "world_model_latest", {}) or {})
    if payload:
        payload.setdefault("ok", True)
        payload.setdefault("schema_version", WORLD_MODEL_SCHEMA_VERSION)
        return _apply_world_model_freshness(payload)
    return {
        "ok": False,
        "missing": True,
        "schema_version": WORLD_MODEL_SCHEMA_VERSION,
        "hint": "run: zero ai runtime run",
        "time_utc": _utc_now(),
        "domains": {},
        "facts": [],
    }
