from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from zero_os.risk_engine import autonomous_thresholds


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_utc(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _assistant_dir(cwd: str) -> Path:
    path = Path(cwd).resolve() / ".zero_os" / "assistant"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _goals_path(cwd: str) -> Path:
    return _assistant_dir(cwd) / "goals.json"


def _loop_path(cwd: str) -> Path:
    return _assistant_dir(cwd) / "autonomy_loop_state.json"


def _history_path(cwd: str) -> Path:
    return _assistant_dir(cwd) / "autonomy_runs.jsonl"


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


def _append_history(cwd: str, payload: dict) -> None:
    path = _history_path(cwd)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")


def _history_tail(cwd: str, limit: int = 10) -> list[dict]:
    path = _history_path(cwd)
    if not path.exists():
        return []
    rows = [line.strip() for line in path.read_text(encoding="utf-8", errors="replace").splitlines() if line.strip()]
    out: list[dict] = []
    for row in rows[-limit:]:
        try:
            out.append(json.loads(row))
        except json.JSONDecodeError:
            continue
    return out


def _goal_state_default() -> dict:
    return {
        "schema_version": 1,
        "updated_utc": _utc_now(),
        "current_goal_id": "",
        "goals": [],
    }


def _loop_state_default() -> dict:
    return {
        "enabled": False,
        "interval_seconds": 360,
        "last_run_utc": "",
        "next_run_utc": "",
        "last_result_ok": None,
        "last_goal_id": "",
        "last_goal_title": "",
        "last_action_kind": "",
        "last_failure": "",
        "consecutive_failures": 0,
        "backoff_seconds": 0,
        "updated_utc": _utc_now(),
    }


def _normalize_goal(goal: dict) -> dict:
    normalized = {
        "id": str(goal.get("id") or str(uuid.uuid4())[:10]),
        "key": str(goal.get("key") or ""),
        "title": str(goal.get("title") or "Untitled goal"),
        "description": str(goal.get("description") or ""),
        "priority": int(goal.get("priority", 50)),
        "source": str(goal.get("source") or "system"),
        "state": str(goal.get("state") or "open"),
        "risk": str(goal.get("risk") or "low"),
        "action_kind": str(goal.get("action_kind") or "inspect_status"),
        "action_args": dict(goal.get("action_args") or {}),
        "next_action": str(goal.get("next_action") or ""),
        "requires_user": bool(goal.get("requires_user", False)),
        "blocked_reason": str(goal.get("blocked_reason") or ""),
        "attempts": int(goal.get("attempts", 0)),
        "last_result_ok": goal.get("last_result_ok"),
        "last_result_summary": str(goal.get("last_result_summary") or ""),
        "created_utc": str(goal.get("created_utc") or _utc_now()),
        "updated_utc": str(goal.get("updated_utc") or _utc_now()),
        "resolved_utc": str(goal.get("resolved_utc") or ""),
        "evidence": dict(goal.get("evidence") or {}),
        "managed": bool(goal.get("managed", True)),
    }
    if normalized["requires_user"] and normalized["state"] == "open":
        normalized["state"] = "blocked"
    return normalized


def _load_goals(cwd: str) -> dict:
    state = _load(_goals_path(cwd), _goal_state_default())
    state.setdefault("schema_version", 1)
    state.setdefault("current_goal_id", "")
    state["goals"] = [_normalize_goal(goal) for goal in state.get("goals", [])]
    state["updated_utc"] = _utc_now()
    return state


def _save_goals(cwd: str, state: dict) -> dict:
    state["updated_utc"] = _utc_now()
    _save(_goals_path(cwd), state)
    return state


def _load_loop(cwd: str) -> dict:
    state = _load(_loop_path(cwd), _loop_state_default())
    default = _loop_state_default()
    for key, value in default.items():
        state.setdefault(key, value)
    state["updated_utc"] = _utc_now()
    return state


def _save_loop(cwd: str, state: dict) -> dict:
    state["updated_utc"] = _utc_now()
    _save(_loop_path(cwd), state)
    return state


def _goal_sort_key(goal: dict) -> tuple:
    return (
        0 if not bool(goal.get("requires_user", False)) else 1,
        -int(goal.get("priority", 0)),
        str(goal.get("created_utc", "")),
        str(goal.get("id", "")),
    )


def _upsert_goal(
    state: dict,
    *,
    key: str,
    title: str,
    description: str,
    priority: int,
    source: str,
    action_kind: str,
    next_action: str,
    risk: str,
    evidence: dict,
    requires_user: bool = False,
    blocked_reason: str = "",
    action_args: dict | None = None,
    managed: bool = True,
) -> dict:
    now = _utc_now()
    target = next((goal for goal in state["goals"] if goal.get("key") == key), None)
    if target is None:
        target = _normalize_goal(
            {
                "id": str(uuid.uuid4())[:10],
                "key": key,
                "created_utc": now,
                "managed": managed,
            }
        )
        state["goals"].append(target)
    target.update(
        {
            "title": title,
            "description": description,
            "priority": int(priority),
            "source": source,
            "state": "blocked" if requires_user else "open",
            "risk": risk,
            "action_kind": action_kind,
            "action_args": dict(action_args or {}),
            "next_action": next_action,
            "requires_user": bool(requires_user),
            "blocked_reason": blocked_reason if requires_user else "",
            "updated_utc": now,
            "resolved_utc": "",
            "evidence": dict(evidence or {}),
            "managed": managed,
        }
    )
    return target


def _resolve_goal(state: dict, key: str, summary: str = "") -> None:
    now = _utc_now()
    for goal in state["goals"]:
        if goal.get("key") != key:
            continue
        goal["state"] = "resolved"
        goal["blocked_reason"] = ""
        goal["updated_utc"] = now
        if not goal.get("resolved_utc"):
            goal["resolved_utc"] = now
        if summary:
            goal["last_result_summary"] = summary


def _select_current_goal(state: dict) -> dict | None:
    candidates = [goal for goal in state.get("goals", []) if goal.get("state") in {"open", "blocked"}]
    if not candidates:
        state["current_goal_id"] = ""
        return None
    selected = sorted(candidates, key=_goal_sort_key)[0]
    state["current_goal_id"] = str(selected.get("id", ""))
    return selected


def _collect_signals(cwd: str) -> dict:
    from zero_os.approval_workflow import status as approval_status
    from zero_os.assistant_job_runner import status as job_status
    from zero_os.decision_governor import governor_decide
    from zero_os.zero_ai_control_workflows import zero_ai_control_workflows_status
    from zero_os.phase_runtime import zero_ai_runtime_status
    from zero_os.zero_ai_capability_map import zero_ai_capability_map_status
    from zero_os.zero_ai_evolution import zero_ai_evolution_status
    from zero_os.zero_ai_pressure_harness import pressure_harness_status
    from zero_os.zero_ai_source_evolution import zero_ai_source_evolution_status
    from zero_os.self_continuity import zero_ai_self_continuity_status
    from zero_os.world_model import build_world_model

    runtime = zero_ai_runtime_status(cwd)
    control_workflows = zero_ai_control_workflows_status(cwd)
    capability_map = zero_ai_capability_map_status(cwd)
    evolution = zero_ai_evolution_status(cwd)
    source_evolution = zero_ai_source_evolution_status(cwd)
    continuity = zero_ai_self_continuity_status(cwd)
    pressure = pressure_harness_status(cwd)
    approvals = approval_status(cwd)
    jobs = job_status(cwd)
    runtime_loop = dict(runtime.get("runtime_loop") or {})
    runtime_agent = dict(runtime.get("runtime_agent") or {})
    continuity_block = dict(continuity.get("continuity") or {})
    contradiction_block = dict(continuity.get("contradiction_detection") or {})
    world_model = build_world_model(
        cwd,
        sources={
            "runtime": runtime,
            "runtime_loop": runtime_loop,
            "runtime_agent": runtime_agent,
            "continuity": continuity,
            "pressure": pressure,
            "control_workflows": control_workflows,
            "capability_control_map": capability_map,
            "zero_engine": dict(runtime.get("zero_engine") or {}),
            "self_derivation": dict(runtime.get("self_derivation") or {}),
            "evolution": evolution,
            "source_evolution": source_evolution,
            "approvals": approvals,
            "jobs": jobs,
        },
    )
    decision_governor = governor_decide(cwd, world_model=world_model)
    return {
        "runtime": runtime,
        "runtime_loop": runtime_loop,
        "runtime_agent": runtime_agent,
        "continuity": continuity,
        "continuity_healthy": bool(continuity_block.get("same_system", False)) and not bool(contradiction_block.get("has_contradiction", False)),
        "continuity_score": float(continuity_block.get("continuity_score", 0.0) or 0.0),
        "control_workflows": control_workflows,
        "capability_control_map": capability_map,
        "pressure": pressure,
        "evolution": evolution,
        "source_evolution": source_evolution,
        "approvals": approvals,
        "jobs": jobs,
        "world_model": world_model,
        "decision_governor": decision_governor,
    }


def _sync_managed_goals(cwd: str, state: dict, signals: dict) -> dict:
    runtime = signals["runtime"]
    runtime_agent = signals["runtime_agent"]
    runtime_loop = signals["runtime_loop"]
    approvals = signals["approvals"]
    jobs = signals["jobs"]
    continuity_healthy = bool(signals["continuity_healthy"])

    runtime_missing = bool(runtime.get("missing", False))
    runtime_ready = bool(runtime.get("runtime_ready", False))
    agent_installed = bool(runtime_agent.get("installed", False))
    agent_running = bool(runtime_agent.get("running", False))
    loop_enabled = bool(runtime_loop.get("enabled", False))
    approvals_count = int(approvals.get("pending_count", approvals.get("count", 0)) or 0)
    jobs_count = int(jobs.get("count", 0))
    evolution = signals["evolution"]
    source_evolution = signals["source_evolution"]

    if not continuity_healthy:
        _upsert_goal(
            state,
            key="restore_continuity",
            title="Restore Zero AI continuity",
            description="Repair continuity drift before autonomous work continues.",
            priority=100,
            source="continuity",
            action_kind="repair_continuity",
            next_action="zero ai self repair restore continuity",
            risk="medium",
            evidence={
                "continuity_score": signals["continuity_score"],
                "has_contradiction": bool((signals["continuity"].get("contradiction_detection") or {}).get("has_contradiction", False)),
            },
        )
    else:
        _resolve_goal(state, "restore_continuity", "continuity stable")

    if runtime_missing or not runtime_ready:
        _upsert_goal(
            state,
            key="stabilize_runtime",
            title="Stabilize Zero AI runtime",
            description="Run the runtime pass to restore a ready autonomous state.",
            priority=95,
            source="runtime",
            action_kind="run_runtime",
            next_action="zero ai runtime run",
            risk="low",
            evidence={
                "runtime_missing": runtime_missing,
                "runtime_ready": runtime_ready,
                "runtime_score": runtime.get("runtime_score"),
            },
        )
    else:
        _resolve_goal(state, "stabilize_runtime", "runtime ready")

    if not agent_installed or not agent_running:
        _upsert_goal(
            state,
            key="ensure_background_agent",
            title="Keep Zero AI always on",
            description="Install and start the background agent so Zero AI can stay active between UI sessions.",
            priority=85,
            source="runtime_agent",
            action_kind="ensure_background_agent",
            next_action="zero ai runtime agent install + start",
            risk="low",
            evidence={"installed": agent_installed, "running": agent_running},
        )
    else:
        _resolve_goal(state, "ensure_background_agent", "background agent active")

    if agent_installed and agent_running and not loop_enabled:
        _upsert_goal(
            state,
            key="enable_runtime_loop",
            title="Enable recurring runtime loop",
            description="Turn on the runtime loop so the background agent has due work to execute.",
            priority=80,
            source="runtime_loop",
            action_kind="enable_runtime_loop",
            next_action="zero ai runtime loop on interval=180",
            risk="low",
            evidence={"enabled": loop_enabled, "interval_seconds": runtime_loop.get("interval_seconds", 180)},
        )
    else:
        _resolve_goal(state, "enable_runtime_loop", "runtime loop enabled or agent not ready")

    if jobs_count > 0:
        _upsert_goal(
            state,
            key="process_assistant_queue",
            title="Process queued assistant work",
            description="Run the assistant job queue so pending tasks do not stall.",
            priority=75,
            source="jobs",
            action_kind="jobs_tick",
            next_action="zero ai jobs tick",
            risk="low",
            evidence={"queued_jobs": jobs_count, "recurring_jobs": int(jobs.get("recurring_count", 0))},
        )
    else:
        _resolve_goal(state, "process_assistant_queue", "assistant queue clear")

    evolution_ready = bool(evolution.get("self_evolution_ready", False))
    evolution_due = bool(evolution.get("due_now", False))
    evolution_action = str(evolution.get("recommended_action", "observe"))
    evolution_candidate = bool((evolution.get("proposal") or {}).get("candidate_available", False))
    evolution_beneficial = bool((evolution.get("proposal") or {}).get("beneficial", False))
    if (
        continuity_healthy
        and runtime_ready
        and agent_installed
        and agent_running
        and loop_enabled
        and approvals_count == 0
        and jobs_count == 0
        and evolution_ready
        and evolution_due
        and evolution_candidate
        and evolution_beneficial
        and evolution_action in {"auto_run", "promote"}
    ):
        _upsert_goal(
            state,
            key="self_evolve",
            title="Evolve Zero AI safely",
            description="Run a bounded self-evolution pass with canary measurement and rollback safety.",
            priority=70,
            source="self_evolution",
            action_kind="evolution_auto_run",
            next_action="zero ai evolution auto run",
            risk="guarded",
            evidence={
                "recommended_action": evolution_action,
                "predicted_gain": (evolution.get("proposal") or {}).get("predicted_gain", 0.0),
                "current_generation": evolution.get("current_generation", 0),
            },
        )
    else:
        _resolve_goal(state, "self_evolve", "bounded self evolution not needed right now")

    source_evolution_ready = bool(source_evolution.get("source_evolution_ready", False))
    source_evolution_due = bool(source_evolution.get("due_now", False))
    source_evolution_action = str(source_evolution.get("recommended_action", "observe"))
    source_evolution_candidate = bool((source_evolution.get("proposal") or {}).get("candidate_available", False))
    source_evolution_beneficial = bool((source_evolution.get("proposal") or {}).get("beneficial", False))
    if (
        continuity_healthy
        and runtime_ready
        and agent_installed
        and agent_running
        and loop_enabled
        and approvals_count == 0
        and jobs_count == 0
        and int(evolution.get("current_generation", 0) or 0) >= 1
        and source_evolution_ready
        and source_evolution_due
        and source_evolution_candidate
        and source_evolution_beneficial
        and source_evolution_action in {"auto_run", "promote"}
    ):
        _upsert_goal(
            state,
            key="source_evolve",
            title="Align learned source defaults",
            description="Promote safe learned runtime defaults back into Zero AI source code with rollback safety.",
            priority=65,
            source="source_evolution",
            action_kind="source_evolution_auto_run",
            next_action="zero ai source evolution auto run",
            risk="guarded",
            evidence={
                "recommended_action": source_evolution_action,
                "predicted_gain": (source_evolution.get("proposal") or {}).get("predicted_gain", 0.0),
                "current_source_generation": source_evolution.get("current_source_generation", 0),
            },
        )
    else:
        _resolve_goal(state, "source_evolve", "guarded source evolution not needed right now")

    if approvals_count > 0:
        _upsert_goal(
            state,
            key="pending_approvals",
            title="Review pending approvals",
            description="Autonomous work is blocked by approvals that need a human decision.",
            priority=110,
            source="approval",
            action_kind="wait_for_user",
            next_action="review pending approvals",
            risk="human_review",
            evidence={"pending_approvals": approvals_count},
            requires_user=True,
            blocked_reason=f"{approvals_count} approval item(s) are waiting for review",
        )
    else:
        _resolve_goal(state, "pending_approvals", "no pending approvals")

    return state


def _build_status(cwd: str, state: dict, signals: dict) -> dict:
    current = _select_current_goal(state)
    goals = list(state.get("goals", []))
    open_goals = [goal for goal in goals if goal.get("state") == "open"]
    blocked_goals = [goal for goal in goals if goal.get("state") == "blocked"]
    resolved_goals = [goal for goal in goals if goal.get("state") == "resolved"]
    loop = _load_loop(cwd)
    next_run = _parse_utc(str(loop.get("next_run_utc", "")))
    loop_due = bool(loop.get("enabled", False)) and (next_run is None or datetime.now(timezone.utc) >= next_run)
    return {
        "ok": True,
        "goals_path": str(_goals_path(cwd)),
        "loop_path": str(_loop_path(cwd)),
        "thresholds": autonomous_thresholds(),
        "current_goal": current,
        "current_goal_title": str((current or {}).get("title", "")),
        "current_goal_next_action": str((current or {}).get("next_action", "")),
        "blocked_reason": str((current or {}).get("blocked_reason", "")),
        "goal_count": len(goals),
        "open_count": len(open_goals),
        "blocked_count": len(blocked_goals),
        "resolved_count": len(resolved_goals),
        "approvals_pending": int(signals["approvals"].get("pending_count", signals["approvals"].get("count", 0)) or 0),
        "approvals_expired": int(signals["approvals"].get("expired_count", 0) or 0),
        "jobs_pending": int(signals["jobs"].get("count", 0)),
        "runtime_ready": bool(signals["runtime"].get("runtime_ready", False)),
        "continuity_healthy": bool(signals["continuity_healthy"]),
        "control_workflows": signals["control_workflows"],
        "capability_control_map": signals["capability_control_map"],
        "pressure": signals["pressure"],
        "evolution": signals["evolution"],
        "source_evolution": signals["source_evolution"],
        "world_model": signals["world_model"],
        "decision_governor": signals["decision_governor"],
        "top_level_call": str((signals["decision_governor"] or {}).get("call", "observe") or "observe"),
        "evolution_ready": bool((signals["evolution"] or {}).get("self_evolution_ready", False)),
        "evolution_due_now": bool((signals["evolution"] or {}).get("due_now", False)),
        "source_evolution_ready": bool((signals["source_evolution"] or {}).get("source_evolution_ready", False)),
        "source_evolution_due_now": bool((signals["source_evolution"] or {}).get("due_now", False)),
        "autonomy_ready": len(open_goals) == 0 and len(blocked_goals) == 0,
        "loop": {
            **loop,
            "due_now": loop_due,
        },
        "recent_runs": _history_tail(cwd, limit=8),
        "goals": goals,
    }


def zero_ai_autonomy_status(cwd: str) -> dict:
    state = _load_goals(cwd)
    signals = _collect_signals(cwd)
    _sync_managed_goals(cwd, state, signals)
    _save_goals(cwd, state)
    return _build_status(cwd, state, signals)


def zero_ai_autonomy_goals(cwd: str) -> dict:
    return zero_ai_autonomy_status(cwd)


def zero_ai_autonomy_sync(cwd: str) -> dict:
    state = _load_goals(cwd)
    signals = _collect_signals(cwd)
    _sync_managed_goals(cwd, state, signals)
    _save_goals(cwd, state)
    return {
        "ok": True,
        "status": _build_status(cwd, state, signals),
        "signals": {
            "runtime_ready": bool(signals["runtime"].get("runtime_ready", False)),
            "runtime_missing": bool(signals["runtime"].get("missing", False)),
            "continuity_healthy": bool(signals["continuity_healthy"]),
            "approvals_pending": int(signals["approvals"].get("pending_count", signals["approvals"].get("count", 0)) or 0),
            "approvals_expired": int(signals["approvals"].get("expired_count", 0) or 0),
            "jobs_pending": int(signals["jobs"].get("count", 0)),
            "fully_autonomous_control": bool((signals["capability_control_map"] or {}).get("fully_autonomous_control", False)),
            "self_evolution_ready": bool((signals["evolution"] or {}).get("self_evolution_ready", False)),
            "self_evolution_due_now": bool((signals["evolution"] or {}).get("due_now", False)),
            "governor_call": str((signals["decision_governor"] or {}).get("call", "observe") or "observe"),
            "governor_mode": str((signals["decision_governor"] or {}).get("mode", "normal") or "normal"),
        },
    }


def zero_ai_autonomy_add_goal(cwd: str, goal_text: str, priority: int = 70) -> dict:
    title = goal_text.strip()
    if not title:
        return {"ok": False, "reason": "empty_goal"}
    state = _load_goals(cwd)
    slug = "".join(ch.lower() if ch.isalnum() else "_" for ch in title).strip("_") or "manual_goal"
    key = f"manual_{slug}"
    _upsert_goal(
        state,
        key=key,
        title=title,
        description=title,
        priority=max(1, min(100, int(priority))),
        source="manual",
        action_kind="request_task",
        next_action=title,
        risk="variable",
        evidence={"manual_goal": True},
        action_args={"request": title},
        managed=False,
    )
    _save_goals(cwd, state)
    return {"ok": True, "status": zero_ai_autonomy_status(cwd), "added_goal_key": key}


def _execute_goal_action(cwd: str, goal: dict) -> dict:
    action_kind = str(goal.get("action_kind", ""))
    action_args = dict(goal.get("action_args") or {})

    if action_kind == "repair_continuity":
        from zero_os.self_continuity import zero_ai_self_repair_restore_continuity

        result = zero_ai_self_repair_restore_continuity(cwd)
        return {"ok": bool(result.get("ok", False)), "action_kind": action_kind, "result": result}

    if action_kind == "run_runtime":
        from zero_os.phase_runtime import zero_ai_runtime_run

        result = zero_ai_runtime_run(cwd, skip_autonomy_background=True)
        return {"ok": bool(result.get("ok", False)), "action_kind": action_kind, "result": result}

    if action_kind == "ensure_background_agent":
        from zero_os.phase_runtime import zero_ai_runtime_agent_ensure, zero_ai_runtime_agent_status

        ensure = zero_ai_runtime_agent_ensure(cwd)
        final_status = zero_ai_runtime_agent_status(cwd)
        return {
            "ok": bool(final_status.get("installed", False)) and bool(final_status.get("running", False)),
            "action_kind": action_kind,
            "steps": [ensure],
            "result": final_status,
        }

    if action_kind == "enable_runtime_loop":
        from zero_os.phase_runtime import zero_ai_runtime_loop_set

        result = zero_ai_runtime_loop_set(cwd, True, int(action_args.get("interval_seconds", 180) or 180))
        return {"ok": bool(result.get("enabled", False)), "action_kind": action_kind, "result": result}

    if action_kind == "jobs_tick":
        from zero_os.assistant_job_runner import tick as job_tick

        result = job_tick(cwd)
        return {"ok": bool(result.get("ok", False)), "action_kind": action_kind, "result": result}

    if action_kind == "evolution_auto_run":
        from zero_os.zero_ai_evolution import zero_ai_evolution_auto_run

        result = zero_ai_evolution_auto_run(cwd)
        return {"ok": bool(result.get("ok", False)), "action_kind": action_kind, "result": result}

    if action_kind == "source_evolution_auto_run":
        from zero_os.zero_ai_source_evolution import zero_ai_source_evolution_auto_run

        result = zero_ai_source_evolution_auto_run(cwd)
        return {"ok": bool(result.get("ok", False)), "action_kind": action_kind, "result": result}

    if action_kind == "request_task":
        from zero_os.task_executor import run_task

        request = str(action_args.get("request") or goal.get("next_action") or goal.get("title") or "")
        result = run_task(cwd, request)
        return {"ok": bool(result.get("ok", False)), "action_kind": action_kind, "result": result}

    if action_kind == "inspect_status":
        from zero_os.phase_runtime import zero_ai_runtime_status

        result = zero_ai_runtime_status(cwd)
        return {"ok": True, "action_kind": action_kind, "result": result}

    if action_kind == "wait_for_user":
        return {
            "ok": True,
            "action_kind": action_kind,
            "result": {"ok": True, "ran": False, "reason": str(goal.get("blocked_reason") or "waiting_for_user")},
        }

    return {"ok": False, "action_kind": action_kind, "result": {"ok": False, "reason": f"unknown_action_kind:{action_kind}"}}


def zero_ai_autonomy_run(cwd: str) -> dict:
    synced = zero_ai_autonomy_sync(cwd)
    state = _load_goals(cwd)
    current = _select_current_goal(state)
    _save_goals(cwd, state)

    if current is None:
        record = {"time_utc": _utc_now(), "ran": False, "ok": True, "reason": "no actionable goals"}
        _append_history(cwd, record)
        return {"ok": True, "ran": False, "reason": "no actionable goals", "autonomy": synced["status"]}

    if bool(current.get("requires_user", False)) or current.get("state") == "blocked":
        record = {
            "time_utc": _utc_now(),
            "ran": False,
            "ok": True,
            "goal_id": current.get("id"),
            "goal_title": current.get("title"),
            "reason": current.get("blocked_reason") or "goal blocked for user review",
        }
        _append_history(cwd, record)
        return {
            "ok": True,
            "ran": False,
            "reason": str(current.get("blocked_reason") or "goal blocked for user review"),
            "goal": current,
            "autonomy": synced["status"],
        }

    execution = _execute_goal_action(cwd, current)
    state = _load_goals(cwd)
    target = next((goal for goal in state["goals"] if goal.get("id") == current.get("id")), None)
    if target is not None:
        target["attempts"] = int(target.get("attempts", 0)) + 1
        target["last_result_ok"] = bool(execution.get("ok", False))
        target["last_result_summary"] = str(
            execution.get("result", {}).get("reason")
            or execution.get("result", {}).get("summary")
            or execution.get("action_kind", "")
        )
        target["updated_utc"] = _utc_now()
        if not bool(target.get("managed", True)) and bool(execution.get("ok", False)):
            target["state"] = "resolved"
            target["resolved_utc"] = _utc_now()
    _save_goals(cwd, state)
    final_sync = zero_ai_autonomy_sync(cwd)
    record = {
        "time_utc": _utc_now(),
        "ran": True,
        "ok": bool(execution.get("ok", False)),
        "goal_id": current.get("id"),
        "goal_title": current.get("title"),
        "action_kind": execution.get("action_kind"),
        "summary": str(
            execution.get("result", {}).get("reason")
            or execution.get("result", {}).get("summary")
            or execution.get("action_kind", "")
        ),
    }
    _append_history(cwd, record)
    return {
        "ok": bool(execution.get("ok", False)),
        "ran": True,
        "goal": current,
        "execution": execution,
        "autonomy": final_sync["status"],
    }


def zero_ai_autonomy_drain(cwd: str, max_runs: int = 8) -> dict:
    attempts = max(1, min(32, int(max_runs)))
    runs: list[dict] = []
    for _ in range(attempts):
        status = zero_ai_autonomy_status(cwd)
        current = dict(status.get("current_goal") or {})
        if not current:
            return {"ok": True, "ran": bool(runs), "reason": "no actionable goals", "runs": runs, "status": status}
        if str(current.get("state", "")) == "blocked":
            return {"ok": True, "ran": bool(runs), "reason": str(current.get("blocked_reason") or "blocked_goal"), "runs": runs, "status": status}
        run = zero_ai_autonomy_run(cwd)
        runs.append(run)
        if not bool(run.get("ran", False)):
            break
        if not bool(run.get("ok", False)):
            return {"ok": False, "ran": True, "reason": str(run.get("reason", "autonomy drain failed")), "runs": runs, "status": zero_ai_autonomy_status(cwd)}
    return {
        "ok": True,
        "ran": bool(runs),
        "reason": "max_runs_reached" if len(runs) >= attempts else "idle",
        "runs": runs,
        "status": zero_ai_autonomy_status(cwd),
    }


def zero_ai_autonomy_loop_status(cwd: str) -> dict:
    state = _load_loop(cwd)
    next_run = _parse_utc(str(state.get("next_run_utc", "")))
    due_now = bool(state.get("enabled", False)) and (next_run is None or datetime.now(timezone.utc) >= next_run)
    _save_loop(cwd, state)
    return {
        "ok": True,
        "loop_path": str(_loop_path(cwd)),
        "due_now": due_now,
        "autonomy": zero_ai_autonomy_status(cwd),
        **state,
    }


def zero_ai_autonomy_loop_set(cwd: str, enabled: bool, interval_seconds: int | None = None) -> dict:
    state = _load_loop(cwd)
    state["enabled"] = bool(enabled)
    if interval_seconds is not None:
        state["interval_seconds"] = max(60, min(3600, int(interval_seconds)))
    if enabled:
        state["next_run_utc"] = _utc_now()
    else:
        state["next_run_utc"] = ""
        state["backoff_seconds"] = 0
    _save_loop(cwd, state)
    return zero_ai_autonomy_loop_status(cwd)


def _loop_delay_seconds(interval_seconds: int, consecutive_failures: int) -> int:
    base = max(60, min(3600, int(interval_seconds)))
    failures = max(0, int(consecutive_failures))
    if failures <= 0:
        return base
    return min(3600, base * (2 ** min(failures - 1, 4)))


def zero_ai_autonomy_loop_tick(cwd: str, force: bool = False) -> dict:
    state = _load_loop(cwd)
    if not bool(state.get("enabled", False)) and not force:
        _save_loop(cwd, state)
        return {"ok": True, "ran": False, "reason": "autonomy loop is off", "autonomy_loop": zero_ai_autonomy_loop_status(cwd)}

    now = datetime.now(timezone.utc)
    next_run = _parse_utc(str(state.get("next_run_utc", "")))
    if not force and next_run is not None and now < next_run:
        _save_loop(cwd, state)
        return {"ok": True, "ran": False, "reason": "autonomy loop not due", "autonomy_loop": zero_ai_autonomy_loop_status(cwd)}

    started = datetime.now(timezone.utc)
    try:
        result = zero_ai_autonomy_run(cwd)
    except Exception as exc:  # pragma: no cover - safety net
        result = {"ok": False, "reason": str(exc), "ran": True}

    finished = datetime.now(timezone.utc)
    ok = bool(result.get("ok", False))
    interval_seconds = max(60, min(3600, int(state.get("interval_seconds", 300))))
    state["last_run_utc"] = finished.isoformat()
    state["last_result_ok"] = ok
    state["last_goal_id"] = str((result.get("goal") or {}).get("id", ""))
    state["last_goal_title"] = str((result.get("goal") or {}).get("title", ""))
    state["last_action_kind"] = str((result.get("execution") or {}).get("action_kind", ""))
    if ok:
        state["consecutive_failures"] = 0
        state["backoff_seconds"] = 0
        state["last_failure"] = ""
        next_delay = interval_seconds
    else:
        state["consecutive_failures"] = int(state.get("consecutive_failures", 0)) + 1
        state["backoff_seconds"] = _loop_delay_seconds(interval_seconds, int(state["consecutive_failures"]))
        state["last_failure"] = str(result.get("reason") or (result.get("execution") or {}).get("result", {}).get("reason", "autonomy loop run failed"))
        next_delay = int(state["backoff_seconds"])
    state["next_run_utc"] = (finished + timedelta(seconds=max(60, next_delay))).isoformat()
    _save_loop(cwd, state)
    return {
        "ok": ok,
        "ran": True,
        "autonomy_loop": zero_ai_autonomy_loop_status(cwd),
        "result": result,
    }


def zero_ai_autonomy_loop_run(cwd: str) -> dict:
    return zero_ai_autonomy_loop_tick(cwd, force=True)
