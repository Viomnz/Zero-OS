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
    if kind in set(policy.get("deny", [])):
        return "forbidden"
    if kind in set(policy.get("approval_required", [])):
        return "approval_gated"
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
    from zero_os.phase_runtime import zero_ai_runtime_agent_status, zero_ai_runtime_loop_status
    from zero_os.self_continuity import zero_ai_self_continuity_status
    from zero_os.zero_ai_control_workflows import zero_ai_control_workflows_status
    from zero_os.zero_ai_evolution import zero_ai_evolution_status
    from zero_os.zero_ai_source_evolution import zero_ai_source_evolution_status

    runtime_status = _load(_runtime_status_path(cwd), {})
    goals_state = _load(_goals_path(cwd), {"goals": []})
    autonomy_loop = _load(_autonomy_loop_path(cwd), {"enabled": False, "interval_seconds": 360})
    policy = policy_status(cwd)
    approvals = approval_status(cwd)
    jobs = jobs_status(cwd)
    runtime_loop = zero_ai_runtime_loop_status(cwd)
    runtime_agent = zero_ai_runtime_agent_status(cwd)
    continuity = zero_ai_self_continuity_status(cwd)
    workflows = zero_ai_control_workflows_status(cwd)
    evolution = zero_ai_evolution_status(cwd)
    source_evolution = zero_ai_source_evolution_status(cwd)
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
        action = str(item.get("action", "")).strip()
        approval_counts[action] = approval_counts.get(action, 0) + 1

    browser_workflow = dict((workflows.get("lanes") or {}).get("browser") or {})
    store_install_workflow = dict((workflows.get("lanes") or {}).get("store_install") or {})
    recovery_workflow = dict((workflows.get("lanes") or {}).get("recovery") or {})

    browser_control = str(browser_workflow.get("control_level") or _policy_decision(policy, "browser_action"))
    store_install_control = str(store_install_workflow.get("control_level") or _policy_decision(policy, "store_install"))
    recovery_control = str(recovery_workflow.get("control_level") or _policy_decision(policy, "recover"))
    self_repair_control = _policy_decision(policy, "self_repair")

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
            "High-risk self repair",
            "self_model",
            self_repair_control,
            active=approval_counts.get("self_repair", 0) == 0,
            ready=True,
            action_kind="self_repair",
            notes="High-risk self-repair remains approval-gated even though continuity repair exists.",
            evidence={"pending_approvals": approval_counts.get("self_repair", 0)},
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
    if approval_gated_count > 0:
        highest_value_steps.append("Convert the remaining approval-gated high-risk self-repair lane into a typed canary-backed autonomous workflow.")
    if forbidden_count > 0:
        highest_value_steps.append("Expand guarded source evolution from allowlisted defaults to a sandboxed patch lane for selected non-identity modules.")
    if not bool(store_install_workflow.get("active", False)):
        highest_value_steps.append("Publish or register at least one store package so the autonomous install workflow has a real target.")
    highest_value_steps.append("Build a subsystem-by-subsystem controller registry so each Zero OS surface has an explicit safe autonomy contract.")

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
        },
        "control_workflows": workflows,
        "capabilities": capabilities,
        "blocking_capabilities": [item for item in capabilities if item["control_level"] != "autonomous"],
        "highest_value_steps": highest_value_steps,
    }
    _save(_map_path(cwd), status)
    return status


def zero_ai_capability_map_refresh(cwd: str) -> dict:
    return zero_ai_capability_map_status(cwd)
