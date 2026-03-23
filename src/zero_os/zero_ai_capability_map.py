from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _assistant_dir(cwd: str) -> Path:
    path = Path(cwd).resolve() / ".zero_os" / "assistant"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _runtime_dir(cwd: str) -> Path:
    path = Path(cwd).resolve() / ".zero_os" / "runtime"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _load(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return default


def _save(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _map_path(cwd: str) -> Path:
    return _assistant_dir(cwd) / "capability_map.json"


def _runtime_status_path(cwd: str) -> Path:
    return _runtime_dir(cwd) / "phase_runtime_status.json"


def _goals_path(cwd: str) -> Path:
    return _assistant_dir(cwd) / "goals.json"


def _autonomy_loop_path(cwd: str) -> Path:
    return _assistant_dir(cwd) / "autonomy_loop_state.json"


def _self_mod_guard_path(cwd: str) -> Path:
    return _runtime_dir(cwd) / "self_modification_guard.json"


def _policy_decision(policy: dict, action_kind: str) -> str:
    kind = action_kind.strip()
    tier = str((policy.get("actions") or {}).get(kind) or "")
    if tier == "forbidden" or kind in set(policy.get("deny", [])):
        return "forbidden"
    if tier == "approval_required" or kind in set(policy.get("approval_required", [])):
        return "approval_gated"
    if tier == "observe_only":
        return "observe_only"
    return "autonomous"


def _capability(
    key: str,
    label: str,
    subsystem: str,
    control_level: str,
    *,
    active: bool,
    ready: bool,
    action_kind: str = "",
    notes: str = "",
    evidence: dict | None = None,
) -> dict:
    return {
        "key": key,
        "label": label,
        "subsystem": subsystem,
        "control_level": control_level,
        "active": bool(active),
        "ready": bool(ready),
        "action_kind": action_kind,
        "notes": notes,
        "evidence": dict(evidence or {}),
    }


def zero_ai_capability_map_status(cwd: str) -> dict:
    from zero_os.agent_permission_policy import policy_status
    from zero_os.approval_workflow import status as approval_status
    from zero_os.assistant_job_runner import status as jobs_status
    from zero_os.contradiction_engine import contradiction_engine_status
    from zero_os.flow_monitor import flow_status
    from zero_os.general_agent_orchestrator import general_agent_orchestrator_status
    from zero_os.smart_workspace import workspace_status
    from zero_os.capability_expansion_protocol import capability_expansion_protocol_status
    from zero_os.calendar_time import calendar_time_status
    from zero_os.communications import communications_status
    from zero_os.domain_pack_factory import domain_pack_factory_status
    from zero_os.phase_runtime import zero_ai_runtime_agent_status, zero_ai_runtime_loop_status
    from zero_os.self_continuity import zero_ai_self_continuity_status
    from zero_os.task_planner import planner_feedback_status
    from zero_os.self_derivation_engine import self_derivation_status
    from zero_os.zero_ai_pressure_harness import pressure_harness_status
    from zero_os.zero_ai_control_workflows import zero_ai_control_workflows_status
    from zero_os.zero_ai_evolution import zero_ai_evolution_status
    from zero_os.zero_ai_source_evolution import zero_ai_source_evolution_status

    runtime_status = _load(_runtime_status_path(cwd), {})
    runtime_self_derivation_background = dict(runtime_status.get("self_derivation_background") or {})
    goals_state = _load(_goals_path(cwd), {"goals": []})
    autonomy_loop = _load(_autonomy_loop_path(cwd), {"enabled": False, "interval_seconds": 360})
    policy = policy_status(cwd)
    approvals = approval_status(cwd)
    jobs = jobs_status(cwd)
    contradiction_engine = contradiction_engine_status(cwd)
    pressure_harness = pressure_harness_status(cwd)
    planner_feedback = planner_feedback_status(cwd)
    self_derivation = self_derivation_status(cwd)
    flow_monitor = flow_status(cwd)
    general_agent = general_agent_orchestrator_status(cwd)
    smart_workspace = workspace_status(cwd)
    runtime_loop = zero_ai_runtime_loop_status(cwd)
    runtime_agent = zero_ai_runtime_agent_status(cwd)
    continuity = zero_ai_self_continuity_status(cwd)
    workflows = zero_ai_control_workflows_status(cwd)
    evolution = zero_ai_evolution_status(cwd)
    source_evolution = zero_ai_source_evolution_status(cwd)
    expansion_protocol = capability_expansion_protocol_status(cwd)
    communications = communications_status(cwd)
    calendar_time = calendar_time_status(cwd)
    domain_pack_factory = domain_pack_factory_status(cwd)
    guard = _load(
        _self_mod_guard_path(cwd),
        {
            "allowed_scopes": ["runtime_tuning", "threshold_updates"],
            "forbidden_scopes": ["identity_core_erase"],
        },
    )

    continuity_block = dict(continuity.get("continuity") or {})
    contradiction_block = dict(continuity.get("contradiction_detection") or {})
    continuity_healthy = bool(continuity_block.get("same_system", False)) and not bool(contradiction_block.get("has_contradiction", False))
    runtime_ready = bool(runtime_status.get("runtime_ready", False))
    runtime_score = float(runtime_status.get("runtime_score", 0.0) or 0.0)
    open_goals = [goal for goal in goals_state.get("goals", []) if str(goal.get("state", "")) == "open"]
    blocked_goals = [goal for goal in goals_state.get("goals", []) if str(goal.get("state", "")) == "blocked"]

    approval_counts: dict[str, int] = {}
    for item in approvals.get("items", []):
        if str(item.get("state", "")).strip() != "pending":
            continue
        action = str(item.get("action", "")).strip()
        approval_counts[action] = approval_counts.get(action, 0) + 1

    browser_workflow = dict((workflows.get("lanes") or {}).get("browser") or {})
    store_install_workflow = dict((workflows.get("lanes") or {}).get("store_install") or {})
    recovery_workflow = dict((workflows.get("lanes") or {}).get("recovery") or {})
    self_repair_workflow = dict((workflows.get("lanes") or {}).get("self_repair") or {})

    browser_control = str(browser_workflow.get("control_level") or _policy_decision(policy, "browser_action"))
    store_install_control = str(store_install_workflow.get("control_level") or _policy_decision(policy, "store_install"))
    recovery_control = str(recovery_workflow.get("control_level") or _policy_decision(policy, "recover"))
    self_repair_control = str(self_repair_workflow.get("control_level") or _policy_decision(policy, "self_repair"))
    planner_feedback_summary = dict(planner_feedback.get("summary") or {})
    planner_feedback_routes = dict(planner_feedback_summary.get("routes") or {})
    planner_history_count = int(planner_feedback_summary.get("history_count", 0) or 0)
    derivation_strategy_freshness_score = float(self_derivation.get("strategy_freshness_score", 0.0) or 0.0)
    derivation_stale_strategy_count = int(self_derivation.get("stale_strategy_count", 0) or 0)
    derivation_version_mismatch_count = int(self_derivation.get("version_mismatch_count", 0) or 0)
    derivation_quarantined_strategy_count = int(self_derivation.get("quarantined_strategy_count", 0) or 0)
    derivation_revalidation_ready_count = int(self_derivation.get("revalidation_ready_count", 0) or 0)
    derivation_top_recovery_profile = str(self_derivation.get("top_recovery_profile", "neutral") or "neutral")
    derivation_runtime_revalidation_state = "ran" if bool(runtime_self_derivation_background.get("ran", False)) else "idle"
    derivation_runtime_revalidation_restored_count = int(runtime_self_derivation_background.get("restored_count", 0) or 0)
    derivation_runtime_revalidation_kept_quarantined_count = int(runtime_self_derivation_background.get("kept_quarantined_count", 0) or 0)
    derivation_runtime_revalidation_reason = str(runtime_self_derivation_background.get("reason", "") or "")
    strategy_drift = dict(pressure_harness.get("strategy_drift") or {})
    strategy_drift_trend = dict(strategy_drift.get("trend") or {})
    strategy_drift_history = dict(strategy_drift.get("history_view") or {})
    strategy_trend_direction = str(strategy_drift_trend.get("direction", "unknown") or "unknown")
    strategy_freshness_delta = float(strategy_drift_trend.get("freshness_delta", 0.0) or 0.0)
    strategy_quarantined_delta = int(strategy_drift_trend.get("quarantined_delta", 0) or 0)
    worst_planner_route = ""
    worst_target_drop = -1.0
    worst_hold = -1.0
    for route_name, metrics in planner_feedback_routes.items():
        target_drop_rate = float(metrics.get("target_drop_rate", 0.0) or 0.0)
        contradiction_hold_rate = float(metrics.get("contradiction_hold_rate", 0.0) or 0.0)
        if (target_drop_rate + contradiction_hold_rate) > (worst_target_drop + worst_hold):
            worst_planner_route = str(route_name)
            worst_target_drop = target_drop_rate
            worst_hold = contradiction_hold_rate
    planner_route_quality_score = 100.0
    if planner_history_count > 0:
        planner_route_quality_score = round(max(0.0, 100.0 - ((max(0.0, worst_target_drop) + max(0.0, worst_hold)) * 50.0)), 2)

    capabilities = [
        _capability(
            "runtime_orchestrator",
            "Runtime orchestrator",
            "runtime",
            "autonomous",
            active=runtime_ready,
            ready=bool(runtime_status),
            action_kind="run_runtime",
            notes="Zero AI can run the main runtime health and orchestration pass without approval.",
            evidence={"runtime_ready": runtime_ready, "runtime_score": runtime_score},
        ),
        _capability(
            "background_agent",
            "Background runtime agent",
            "runtime",
            "autonomous",
            active=bool(runtime_agent.get("installed", False)) and bool(runtime_agent.get("running", False)),
            ready=bool(runtime_agent.get("ok", False)),
            action_kind="ensure_background_agent",
            notes="Keeps Zero AI alive between UI sessions.",
            evidence={
                "installed": bool(runtime_agent.get("installed", False)),
                "running": bool(runtime_agent.get("running", False)),
                "auto_start_on_login": bool(runtime_agent.get("auto_start_on_login", False)),
            },
        ),
        _capability(
            "runtime_loop",
            "Runtime loop",
            "runtime",
            "autonomous",
            active=bool(runtime_loop.get("enabled", False)),
            ready=bool(runtime_loop.get("ok", False)),
            action_kind="enable_runtime_loop",
            notes="Recurring runtime work can execute on a timer without user involvement.",
            evidence={
                "enabled": bool(runtime_loop.get("enabled", False)),
                "interval_seconds": int(runtime_loop.get("interval_seconds", 0) or 0),
            },
        ),
        _capability(
            "autonomy_goal_manager",
            "Autonomy goal manager",
            "autonomy",
            "autonomous",
            active=len(open_goals) == 0 and len(blocked_goals) == 0,
            ready=True,
            action_kind="jobs_tick",
            notes="Selects and runs managed goals inside bounded action lanes.",
            evidence={
                "open_goals": len(open_goals),
                "blocked_goals": len(blocked_goals),
                "loop_enabled": bool(autonomy_loop.get("enabled", False)),
            },
        ),
        _capability(
            "general_agent_orchestrator",
            "General agent orchestrator",
            "general_agent",
            "autonomous",
            active=bool(general_agent.get("general_purpose_ready", False)),
            ready=bool(general_agent.get("ok", False)),
            action_kind="general_agent",
            notes="Assesses broad user requests, selects the subsystems needed to satisfy them, and keeps execution bounded to stable contracts.",
            evidence={
                "agentic_ready": bool(general_agent.get("agentic_ready", False)),
                "required_subsystem_count": int(general_agent.get("required_subsystem_count", 0) or 0),
                "blocked_subsystem_count": int(general_agent.get("blocked_subsystem_count", 0) or 0),
                "recommended_mode": str(general_agent.get("recommended_mode", "")),
            },
        ),
        _capability(
            "smart_workspace_map",
            "Smart workspace map",
            "observation",
            "autonomous",
            active=bool(smart_workspace.get("active", False)),
            ready=bool(smart_workspace.get("ready", False)),
            action_kind="workspace_refresh",
            notes="Maintains an indexed map of the workspace so Zero AI can track structure, symbols, git changes, and live flow state together.",
            evidence={
                "indexed": bool((smart_workspace.get("summary") or {}).get("indexed", False)),
                "search_ready": bool((smart_workspace.get("summary") or {}).get("search_ready", False)),
                "file_count": int((smart_workspace.get("summary") or {}).get("file_count", 0) or 0),
                "git_dirty": bool((smart_workspace.get("summary") or {}).get("git_dirty", False)),
                "git_change_count": int((smart_workspace.get("summary") or {}).get("git_change_count", 0) or 0),
            },
        ),
        _capability(
            "integrity_flow_monitor",
            "Integrity flow monitor",
            "observation",
            "autonomous",
            active=bool(flow_monitor.get("active", False)),
            ready=bool(flow_monitor.get("ready", False)),
            action_kind="flow_scan",
            notes="Aggregates contradiction, source bugs/errors, recent execution failures, and antivirus signals into one smooth observation lane.",
            evidence={
                "flow_score": float((flow_monitor.get("summary") or {}).get("flow_score", 0.0) or 0.0),
                "issue_count": int((flow_monitor.get("summary") or {}).get("issue_count", 0) or 0),
                "highest_severity": str((flow_monitor.get("summary") or {}).get("highest_severity", "")),
                "source_scan_available": bool((flow_monitor.get("summary") or {}).get("source_scan_available", False)),
            },
        ),
        _capability(
            "contradiction_gate",
            "Contradiction gate",
            "reasoning",
            "autonomous",
            active=bool(contradiction_engine.get("active", False)),
            ready=bool(contradiction_engine.get("ready", False)),
            action_kind="contradiction_review",
            notes="Reviews goal, context, evidence, consequence, and self-continuity before output is rendered.",
            evidence={
                "last_decision": str(contradiction_engine.get("last_decision", "")),
                "last_contradiction_count": int(contradiction_engine.get("last_contradiction_count", 0) or 0),
                "continuity_has_contradiction": bool((contradiction_engine.get("continuity") or {}).get("has_contradiction", False)),
                "checks": list(contradiction_engine.get("checks", [])),
            },
        ),
        _capability(
            "pressure_harness",
            "Pressure harness",
            "pressure",
            "autonomous",
            active=not bool(pressure_harness.get("missing", False)),
            ready=True,
            action_kind="pressure_harness_run",
            notes="Runs isolated survivability checks across approvals, contradiction gating, routing, and task completion.",
            evidence={
                "status": str(pressure_harness.get("status", "missing")),
                "scenario_count": int(pressure_harness.get("scenario_count", 0) or 0),
                "failed_count": int(pressure_harness.get("failed_count", 0) or 0),
                "overall_score": float(pressure_harness.get("overall_score", 0.0) or 0.0),
                "top_failure_code": str(pressure_harness.get("top_failure_code", "")),
                "last_run_utc": str(pressure_harness.get("generated_utc", "")),
                "planner_feedback_history_count": planner_history_count,
                "planner_feedback_worst_route": worst_planner_route,
                "planner_feedback_target_drop_rate": round(max(0.0, worst_target_drop), 3),
                "planner_feedback_contradiction_hold_rate": round(max(0.0, worst_hold), 3),
                "strategy_trend_direction": strategy_trend_direction,
                "strategy_freshness_delta": round(strategy_freshness_delta, 3),
                "strategy_quarantined_delta": strategy_quarantined_delta,
                "strategy_history_point_count": int(strategy_drift_history.get("point_count", 0) or 0),
            },
        ),
        _capability(
            "self_derivation_engine",
            "Self derivation engine",
            "reasoning",
            "autonomous",
            active=bool(dict(self_derivation.get("latest") or {}).get("generated_count", 0)),
            ready=True,
            action_kind="self_derivation_assess",
            notes="Generates diverse interpretations, pressures them under bounded laws, and stores surviving structures as reusable knowledge.",
            evidence={
                "generated_count": int(dict(self_derivation.get("latest") or {}).get("generated_count", 0) or 0),
                "survivor_count": int(dict(self_derivation.get("latest") or {}).get("survivor_count", 0) or 0),
                "pattern_count": int(self_derivation.get("pattern_count", 0) or 0),
                "knowledge_count": int(self_derivation.get("knowledge_count", 0) or 0),
                "meta_rule_count": int(self_derivation.get("meta_rule_count", 0) or 0),
                "strategy_outcome_count": int(self_derivation.get("strategy_outcome_count", 0) or 0),
                "strategy_freshness_score": derivation_strategy_freshness_score,
                "stale_strategy_count": derivation_stale_strategy_count,
                "version_mismatch_count": derivation_version_mismatch_count,
                "quarantined_strategy_count": derivation_quarantined_strategy_count,
                "revalidation_ready_count": derivation_revalidation_ready_count,
                "branch_shape_profile_count": int(self_derivation.get("branch_shape_profile_count", 0) or 0),
                "condition_profile_count": int(self_derivation.get("condition_profile_count", 0) or 0),
                "condition_surface_counts": dict(self_derivation.get("condition_surface_counts") or {}),
                "top_recovery_profile": derivation_top_recovery_profile,
                "strategy_trend_direction": strategy_trend_direction,
                "strategy_freshness_delta": round(strategy_freshness_delta, 3),
                "strategy_quarantined_delta": strategy_quarantined_delta,
                "strategy_history": strategy_drift_history,
                "strategy_history_points": list(strategy_drift_history.get("points") or []),
                "strategy_history_path": str(strategy_drift_history.get("path", "")),
                "latest_revalidation": dict(self_derivation.get("latest_revalidation") or {}),
                "runtime_revalidation_state": derivation_runtime_revalidation_state,
                "runtime_revalidation_restored_count": derivation_runtime_revalidation_restored_count,
                "runtime_revalidation_kept_quarantined_count": derivation_runtime_revalidation_kept_quarantined_count,
                "runtime_revalidation_reason": derivation_runtime_revalidation_reason,
                "planner_version": str(self_derivation.get("planner_version", "")),
                "code_version": str(self_derivation.get("code_version", "")),
                "recommended_branch_id": str(dict(self_derivation.get("latest") or {}).get("recommended_branch_id", "")),
            },
        ),
        _capability(
            "continuity_guard",
            "Continuity guard",
            "self_model",
            "autonomous",
            active=continuity_healthy,
            ready=True,
            action_kind="repair_continuity",
            notes="Detects contradiction in self and can restore continuity inside the current identity policy.",
            evidence={
                "continuity_score": float(continuity_block.get("continuity_score", 0.0) or 0.0),
                "same_system": bool(continuity_block.get("same_system", False)),
                "has_contradiction": bool(contradiction_block.get("has_contradiction", False)),
            },
        ),
        _capability(
            "bounded_self_evolution",
            "Bounded self evolution",
            "evolution",
            "autonomous",
            active=bool(evolution.get("self_evolution_ready", False)),
            ready=bool(evolution.get("ok", False)),
            action_kind="evolution_auto_run",
            notes="Can evolve loop tuning inside bounded scopes with canary checks and rollback.",
            evidence={
                "generation": int(evolution.get("current_generation", 0) or 0),
                "recommended_action": str(evolution.get("recommended_action", "")),
            },
        ),
        _capability(
            "guarded_source_evolution",
            "Guarded source evolution",
            "evolution",
            "autonomous",
            active=bool(source_evolution.get("source_evolution_ready", False)),
            ready=bool(source_evolution.get("ok", False)),
            action_kind="source_evolution_auto_run",
            notes="Can promote learned defaults back into an allowlisted source lane with canary verification.",
            evidence={
                "source_generation": int(source_evolution.get("current_source_generation", 0) or 0),
                "recommended_action": str(source_evolution.get("recommended_action", "")),
                "sandbox_patch_scope_count": int(source_evolution.get("sandbox_patch_scope_count", 0) or 0),
                "expanded_sandbox_patch_lane": bool(source_evolution.get("expanded_sandbox_patch_lane", False)),
            },
        ),
        _capability(
            "capability_expansion_protocol",
            "Capability expansion protocol",
            "expansion",
            "autonomous",
            active=True,
            ready=bool(expansion_protocol.get("ok", False)),
            action_kind="capability_expansion_protocol",
            notes="Defines the admission contract every new Zero AI domain pack must satisfy before joining the live system.",
            evidence={
                "required_contract_count": len(expansion_protocol.get("required_contracts", [])),
                "installed_domain_count": int((expansion_protocol.get("summary") or {}).get("installed_domain_count", 0) or 0),
                "missing_function_count": int((expansion_protocol.get("summary") or {}).get("missing_function_count", 0) or 0),
            },
        ),
        _capability(
            "domain_pack_factory",
            "Domain-pack factory",
            "expansion",
            "autonomous",
            active=True,
            ready=bool(domain_pack_factory.get("ok", False)),
            action_kind="domain_pack_factory",
            notes="Scaffolds and verifies new Zero AI domain packs so expansion follows the protocol by default.",
            evidence={
                "domain_pack_count": int((domain_pack_factory.get("summary") or {}).get("domain_pack_count", 0) or 0),
                "ready_count": int((domain_pack_factory.get("summary") or {}).get("ready_count", 0) or 0),
                "required_contract_count": int((domain_pack_factory.get("summary") or {}).get("required_contract_count", 0) or 0),
            },
        ),
        _capability(
            "communications_lane",
            "Communications lane",
            "communications",
            "autonomous",
            active=bool(communications.get("enabled", True)),
            ready=bool(communications.get("ok", False)),
            action_kind="communications_status",
            notes="Local draft/outbox communication lane with audit-ready state and typed status/refresh commands.",
            evidence={
                "draft_count": int((communications.get("summary") or {}).get("draft_count", 0) or 0),
                "outbox_count": int((communications.get("summary") or {}).get("outbox_count", 0) or 0),
                "audit_count": int((communications.get("summary") or {}).get("audit_count", 0) or 0),
            },
        ),
        _capability(
            "calendar_time_lane",
            "Calendar and time lane",
            "calendar_time",
            "autonomous",
            active=bool(calendar_time.get("enabled", True)),
            ready=bool(calendar_time.get("ok", False)),
            action_kind="calendar_time_status",
            notes="Local reminder and schedule lane with typed status/refresh commands.",
            evidence={
                "reminder_count": int((calendar_time.get("summary") or {}).get("reminder_count", 0) or 0),
                "calendar_item_count": int((calendar_time.get("summary") or {}).get("calendar_item_count", 0) or 0),
                "audit_count": int((calendar_time.get("summary") or {}).get("audit_count", 0) or 0),
            },
        ),
        _capability(
            "browser_control",
            "Browser workflow control",
            "integration",
            browser_control,
            active=bool(browser_workflow.get("active", False)),
            ready=bool(browser_workflow.get("ready", False)),
            action_kind="workflow_browser",
            notes="Raw browser_action requests remain approval-gated, but Zero AI now has a typed canary-backed browser workflow for allowlisted targets.",
            evidence={
                "pending_approvals": approval_counts.get("browser_action", 0),
                "workflow": browser_workflow,
                "raw_action_policy": _policy_decision(policy, "browser_action"),
            },
        ),
        _capability(
            "store_installation",
            "Store install workflow",
            "integration",
            store_install_control,
            active=bool(store_install_workflow.get("active", False)),
            ready=bool(store_install_workflow.get("ready", False)),
            action_kind="workflow_store_install",
            notes="Raw store_install requests remain approval-gated, but Zero AI now has a canary-backed install workflow that can validate and promote installs autonomously.",
            evidence={
                "pending_approvals": approval_counts.get("store_install", 0),
                "workflow": store_install_workflow,
                "raw_action_policy": _policy_decision(policy, "store_install"),
            },
        ),
        _capability(
            "recovery_restore",
            "Recovery workflow",
            "recovery",
            recovery_control,
            active=bool(recovery_workflow.get("active", False)),
            ready=bool(recovery_workflow.get("ready", False)),
            action_kind="workflow_recover",
            notes="Raw recover requests remain approval-gated, but Zero AI now has a canary-backed recovery workflow that validates a snapshot before promotion.",
            evidence={
                "pending_approvals": approval_counts.get("recover", 0),
                "workflow": recovery_workflow,
                "raw_action_policy": _policy_decision(policy, "recover"),
            },
        ),
        _capability(
            "high_risk_self_repair",
            "Self-repair workflow",
            "self_model",
            self_repair_control,
            active=bool(self_repair_workflow.get("active", False)),
            ready=bool(self_repair_workflow.get("ready", False)),
            action_kind="workflow_self_repair",
            notes="Raw self_repair requests remain approval-gated, but Zero AI now has a canary-backed self-repair workflow with rollback to a safe snapshot on failed verification.",
            evidence={
                "pending_approvals": approval_counts.get("self_repair", 0),
                "workflow": self_repair_workflow,
                "raw_action_policy": _policy_decision(policy, "self_repair"),
            },
        ),
        _capability(
            "identity_core_rewrite",
            "Identity-core rewrite",
            "self_model",
            "forbidden",
            active=False,
            ready=False,
            action_kind="identity_core_erase",
            notes="Identity anchors are intentionally not writable by autonomous self-modification.",
            evidence={"forbidden_scopes": list(guard.get("forbidden_scopes", []))},
        ),
        _capability(
            "arbitrary_source_rewrite",
            "Arbitrary source rewrite",
            "evolution",
            "forbidden",
            active=False,
            ready=False,
            notes="Source evolution is allowlisted; arbitrary repo-wide rewriting is intentionally blocked.",
            evidence={"allowed_scopes": list(source_evolution.get("allowed_scopes", []))},
        ),
        _capability(
            "unrestricted_zero_os_control",
            "Unrestricted Zero OS control",
            "platform",
            "forbidden",
            active=False,
            ready=False,
            notes="Zero AI does not have a single unrestricted control lane over every subsystem.",
            evidence={"jobs_pending": int(jobs.get("count", 0) or 0), "policy_has_gates": True},
        ),
    ]

    autonomous_count = sum(1 for item in capabilities if item["control_level"] == "autonomous")
    approval_gated_count = sum(1 for item in capabilities if item["control_level"] == "approval_gated")
    forbidden_count = sum(1 for item in capabilities if item["control_level"] == "forbidden")
    active_autonomous_count = sum(1 for item in capabilities if item["control_level"] == "autonomous" and item["active"])
    total_count = len(capabilities)
    autonomous_surface_score = round((autonomous_count / max(1, total_count)) * 100.0, 2)
    active_autonomous_surface_score = round((active_autonomous_count / max(1, total_count)) * 100.0, 2)

    highest_value_steps: list[str] = []
    if not bool((smart_workspace.get("summary") or {}).get("indexed", False)):
        highest_value_steps.append("Run `zero ai workspace refresh` to build a searchable smart workspace map before broader edits.")
    else:
        highest_value_steps.append("Maintain the smart workspace map so search, symbols, git state, and structure stay current.")
    if not bool((flow_monitor.get("summary") or {}).get("source_scan_available", False)):
        highest_value_steps.append("Run `zero ai flow scan` so Zero AI can detect contradiction, bugs, errors, and virus signals in one pass.")
    else:
        highest_value_steps.append("Maintain the unified flow monitor so contradiction, source, execution, and threat signals stay visible in one lane.")
    if not bool(contradiction_engine.get("active", False)):
        highest_value_steps.append("Build the contradiction engine and make it the gate before output.")
    else:
        highest_value_steps.append("Maintain the contradiction gate and extend typed reasoning checks across more subsystems.")
    if bool(pressure_harness.get("missing", False)):
        highest_value_steps.append("Run `zero ai pressure run` to create a real survivability baseline under approval, contradiction, routing, and task pressure.")
    elif int(pressure_harness.get("failed_count", 0) or 0) > 0:
        highest_value_steps.append(str(pressure_harness.get("recommended_action", "Fix the top pressure-harness failure before expanding autonomy further.")))
    else:
        highest_value_steps.append("Maintain the pressure harness and keep feeding real incidents back into the survivability suite.")
    if planner_history_count == 0:
        highest_value_steps.append("Run more planner-driven tasks so Zero AI has route-quality evidence, not just capability claims.")
    elif worst_planner_route and (worst_target_drop > 0.0 or worst_hold > 0.0):
        highest_value_steps.append(
            f"Lower contradiction holds and dropped targets on planner route `{worst_planner_route}` before broadening that lane further."
        )
    if planner_history_count > 0 and planner_route_quality_score < 85.0:
        highest_value_steps.append("Raise planner route quality before widening more mutating lanes; keep dropped targets and contradiction holds trending down.")
    if derivation_version_mismatch_count > 0:
        highest_value_steps.append("Refresh strategy memory against the current planner/code version so old execution behavior stops dominating after system changes.")
    if derivation_stale_strategy_count > 0 and derivation_strategy_freshness_score < 0.65:
        highest_value_steps.append("Run fresh planner/execution work so self-derivation strategy memory reflects current behavior instead of stale history.")
    if derivation_quarantined_strategy_count > 0:
        highest_value_steps.append("Run `zero ai self derivation revalidate` so quarantined strategy memory can re-earn trust through explicit canary checks under the current planner generation.")
    if strategy_trend_direction == "degrading":
        highest_value_steps.append("Stabilize degrading strategy drift before widening autonomy; freshness is falling or quarantines are rising.")
    if not bool(source_evolution.get("expanded_sandbox_patch_lane", False)):
        highest_value_steps.append("Expand guarded source evolution from allowlisted defaults to a sandboxed patch lane for selected non-identity modules.")
    else:
        highest_value_steps.append("Maintain the expanded sandboxed patch lane and admit new non-identity modules only through allowlisted canaries.")
    if not bool(store_install_workflow.get("active", False)):
        highest_value_steps.append("Publish or register at least one store package so the autonomous install workflow has a real target.")
    highest_value_steps.append("Use the capability expansion protocol so every new Zero AI domain joins through typed contracts, contradiction checks, rollback/audit, and tests.")
    highest_value_steps.append("Use the domain-pack factory so new Zero AI domains are scaffolded and verified through the protocol by default.")
    highest_value_steps.append("Use the general agent orchestrator to assess broad requests before executing them across multiple subsystems.")
    highest_value_steps.append("Use the controller registry to expand typed safe autonomy contracts across more Zero OS subsystems.")

    status = {
        "ok": True,
        "time_utc": _utc_now(),
        "map_path": str(_map_path(cwd)),
        "fully_autonomous_control": False,
        "summary": {
            "total_count": total_count,
            "autonomous_count": autonomous_count,
            "approval_gated_count": approval_gated_count,
            "forbidden_count": forbidden_count,
            "active_autonomous_count": active_autonomous_count,
            "autonomous_surface_score": autonomous_surface_score,
            "active_autonomous_surface_score": active_autonomous_surface_score,
            "planner_feedback_history_count": planner_history_count,
            "planner_feedback_worst_route": worst_planner_route,
            "planner_feedback_target_drop_rate": round(max(0.0, worst_target_drop), 3),
            "planner_feedback_contradiction_hold_rate": round(max(0.0, worst_hold), 3),
            "planner_route_quality_score": planner_route_quality_score,
            "self_derivation_strategy_freshness_score": derivation_strategy_freshness_score,
            "self_derivation_stale_strategy_count": derivation_stale_strategy_count,
            "self_derivation_version_mismatch_count": derivation_version_mismatch_count,
            "self_derivation_quarantined_strategy_count": derivation_quarantined_strategy_count,
            "self_derivation_revalidation_ready_count": derivation_revalidation_ready_count,
            "self_derivation_top_recovery_profile": derivation_top_recovery_profile,
            "self_derivation_runtime_revalidation_state": derivation_runtime_revalidation_state,
            "self_derivation_runtime_revalidation_restored_count": derivation_runtime_revalidation_restored_count,
            "self_derivation_runtime_revalidation_kept_quarantined_count": derivation_runtime_revalidation_kept_quarantined_count,
            "self_derivation_runtime_revalidation_reason": derivation_runtime_revalidation_reason,
            "self_derivation_strategy_trend_direction": strategy_trend_direction,
            "self_derivation_strategy_freshness_delta": round(strategy_freshness_delta, 3),
            "self_derivation_strategy_quarantined_delta": strategy_quarantined_delta,
            "self_derivation_strategy_history_point_count": int(strategy_drift_history.get("point_count", 0) or 0),
        },
        "control_workflows": workflows,
        "capability_expansion_protocol": expansion_protocol,
        "domain_pack_factory": domain_pack_factory,
        "general_agent": general_agent,
        "capabilities": capabilities,
        "blocking_capabilities": [item for item in capabilities if item["control_level"] != "autonomous"],
        "highest_value_steps": highest_value_steps,
    }
    _save(_map_path(cwd), status)
    return status


def zero_ai_capability_map_refresh(cwd: str) -> dict:
    return zero_ai_capability_map_status(cwd)
