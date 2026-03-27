from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

from zero_os.observation_bus import emit_observation, observation_summary
from zero_os.state_registry import boot_state_registry, get_state_store, update_state_store

WORLD_MODEL_SCHEMA_VERSION = 1


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


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
) -> dict[str, Any]:
    return {
        "name": str(name),
        "source": str(source),
        "healthy": bool(healthy),
        "blocking": bool(blocking),
        "confidence": max(0.0, min(1.0, float(confidence))),
        "summary": deepcopy(summary),
    }


def build_world_model(cwd: str, *, sources: dict[str, Any] | None = None) -> dict[str, Any]:
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
    code_target_file_count = _as_int(code_workbench.get("target_file_count", 0))
    code_in_scope_count = _as_int(code_workbench.get("in_scope_count", 0))
    code_out_of_scope_count = _as_int(code_workbench.get("out_of_scope_count", 0))
    code_missing_in_scope_count = _as_int(code_workbench.get("missing_in_scope_count", 0))
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
                blocking=code_requested_mutation and (not code_scope_ready or code_out_of_scope_count > 0),
                severity="warning" if code_requested_mutation and (not code_scope_ready or code_out_of_scope_count > 0) else "info",
                affects=["code_mutation", "verification"],
                details={
                    "requested_code_mutation": code_requested_mutation,
                    "scope_ready": code_scope_ready,
                    "verification_ready": code_verification_ready,
                    "target_file_count": code_target_file_count,
                    "in_scope_count": code_in_scope_count,
                    "out_of_scope_count": code_out_of_scope_count,
                    "missing_in_scope_count": code_missing_in_scope_count,
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
            summary={"pressure_ready": pressure_ready, "overall_score": pressure_score, "missing": pressure_missing},
        ),
        "recovery": _domain(
            name="recovery",
            source="recovery",
            healthy=recovery_ready,
            blocking=recovery_observed and not recovery_ready,
            confidence=0.97,
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
            summary={"pending_count": approvals_pending, "expired_count": approvals_expired},
        ),
        "jobs": _domain(
            name="jobs",
            source="assistant_job_runner",
            healthy=jobs_pending == 0,
            blocking=False,
            confidence=1.0,
            summary={"pending_count": jobs_pending},
        ),
        "self_derivation": _domain(
            name="self_derivation",
            source="self_derivation_engine",
            healthy=_as_bool(self_derivation.get("ok", False)),
            blocking=False,
            confidence=0.9,
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
            summary={
                "ok": _as_bool(zero_engine.get("ok", False)),
                "subsystem_count": _as_int(zero_engine.get("subsystem_count", zero_engine.get("adapter_count", 0))),
            },
        ),
    }
    if code_workbench_observed:
        domains["codebase"] = _domain(
            name="codebase",
            source="code_workbench",
            healthy=code_ready,
            blocking=code_requested_mutation and (not code_scope_ready or code_out_of_scope_count > 0),
            confidence=0.9,
            summary={
                "workspace_ready": code_workspace_ready,
                "requested_code_mutation": code_requested_mutation,
                "scope_ready": code_scope_ready,
                "verification_ready": code_verification_ready,
                "target_file_count": code_target_file_count,
                "in_scope_count": code_in_scope_count,
                "out_of_scope_count": code_out_of_scope_count,
                "missing_in_scope_count": code_missing_in_scope_count,
            },
        )

    blocked_domains = sorted([name for name, domain in domains.items() if bool(domain.get("blocking", False))])
    degraded_domains = sorted([name for name, domain in domains.items() if not bool(domain.get("healthy", False))])
    summary = observation_summary(observations)
    return {
        "ok": True,
        "schema_version": WORLD_MODEL_SCHEMA_VERSION,
        "time_utc": _utc_now(),
        "cwd": str(cwd),
        "domain_count": len(domains),
        "fact_count": len(observations),
        "blocking_domain_count": len(blocked_domains),
        "degraded_domain_count": len(degraded_domains),
        "blocked_domains": blocked_domains,
        "degraded_domains": degraded_domains,
        "observation_summary": summary,
        "domains": domains,
        "facts": observations,
    }


def persist_world_model(cwd: str, world_model: dict[str, Any], *, flush: bool = False) -> dict[str, Any]:
    boot_state_registry(cwd, names=["world_model_latest"])
    return update_state_store(cwd, "world_model_latest", lambda current: deepcopy(world_model), flush=flush)


def world_model_status(cwd: str) -> dict[str, Any]:
    boot_state_registry(cwd, names=["world_model_latest"])
    payload = dict(get_state_store(cwd, "world_model_latest", {}) or {})
    if payload:
        payload.setdefault("ok", True)
        payload.setdefault("schema_version", WORLD_MODEL_SCHEMA_VERSION)
        return payload
    return {
        "ok": False,
        "missing": True,
        "schema_version": WORLD_MODEL_SCHEMA_VERSION,
        "hint": "run: zero ai runtime run",
        "time_utc": _utc_now(),
        "domains": {},
        "facts": [],
    }
