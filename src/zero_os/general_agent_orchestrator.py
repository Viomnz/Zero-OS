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


def _status_path(cwd: str) -> Path:
    return _assistant_dir(cwd) / "general_agent_orchestrator.json"


def _controller_path(cwd: str) -> Path:
    return _assistant_dir(cwd) / "controller_registry.json"


def _capability_path(cwd: str) -> Path:
    return _assistant_dir(cwd) / "capability_map.json"


def _load(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return default


def _save(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _keyword_domains(request: str) -> list[str]:
    lowered = str(request or "").strip().lower()
    domains: list[str] = []

    def add(name: str) -> None:
        if name not in domains:
            domains.append(name)

    add("reasoning")
    if any(token in lowered for token in ("status", "workspace", "observe", "inspect", "bug", "error", "virus", "contradiction")):
        add("observation")
    if any(token in lowered for token in ("runtime", "agent", "background", "loop", "orchestr")):
        add("runtime")
    if any(token in lowered for token in ("goal", "autonomy", "autonomous", "schedule", "tick")):
        add("autonomy")
    if any(token in lowered for token in ("repair", "continuity", "identity", "recover", "restore")):
        add("self_model")
    if any(token in lowered for token in ("browser", "http://", "https://", "web", "github", "api", "cloud", "store")):
        add("integration")
    if any(token in lowered for token in ("message", "email", "draft", "send", "reply", "communications")):
        add("communications")
    if any(token in lowered for token in ("calendar", "time", "reminder", "meeting", "schedule")):
        add("calendar_time")
    if any(token in lowered for token in ("plugin", "mod", "domain pack", "capability expansion", "general-purpose")):
        add("expansion")
    return domains


def _match_subsystem(subsystems: list[dict], key: str) -> dict:
    for item in subsystems:
        if str(item.get("key", "")) == key:
            return dict(item)
    return {
        "key": key,
        "label": key.replace("_", " ").title(),
        "control_level": "forbidden",
        "contract_state": "missing",
        "active": False,
        "ready": False,
        "commands": [],
        "highest_value_step": "install subsystem contract",
    }


def _next_actions(required: list[dict], request: str) -> list[str]:
    actions: list[str] = []
    for item in required:
        key = str(item.get("key", ""))
        control_level = str(item.get("control_level", "forbidden"))
        active = bool(item.get("active", False))
        ready = bool(item.get("ready", False))
        step = str(item.get("highest_value_step", "")).strip()
        if control_level == "forbidden":
            actions.append(f"Expand or admit the `{key}` subsystem before routing `{request}` through Zero AI.")
            continue
        if not ready or not active:
            actions.append(step or f"Make `{key}` ready before bounded execution.")
            continue
        if control_level == "approval_gated":
            actions.append(f"`{key}` is approval-gated. Request approval before execution.")
    if not actions:
        actions.append("Run the request through the bounded execution path.")
    return actions[:4]


def general_agent_orchestrator_status(cwd: str, request: str = "") -> dict:
    from zero_os.domain_pack_factory import domain_pack_factory_status
    from zero_os.structured_intent import extract_intent

    controller = _load(
        _controller_path(cwd),
        {
            "summary": {"active_subsystem_count": 0, "subsystem_count": 0, "missing_function_count": 0},
            "subsystems": [],
        },
    )
    capability_map = _load(
        _capability_path(cwd),
        {
            "summary": {"active_autonomous_surface_score": 0.0},
        },
    )
    domain_factory = domain_pack_factory_status(cwd)
    subsystems = list(controller.get("subsystems") or [])
    summary = dict(controller.get("summary") or {})
    required_domain_keys = _keyword_domains(request) if str(request or "").strip() else [
        "reasoning",
        "observation",
        "runtime",
        "integration",
        "communications",
        "calendar_time",
    ]
    required = [_match_subsystem(subsystems, key) for key in required_domain_keys]
    blocked = [item for item in required if str(item.get("control_level", "")) == "forbidden"]
    approval_gated = [item for item in required if str(item.get("control_level", "")) == "approval_gated"]
    not_ready = [item for item in required if not bool(item.get("ready", False)) or not bool(item.get("active", False))]
    executable = not blocked and not not_ready
    general_surface = float((capability_map.get("summary") or {}).get("active_autonomous_surface_score", 0.0) or 0.0)
    installed_packs = int((domain_factory.get("summary") or {}).get("ready_count", 0) or 0)
    intent = extract_intent(request) if str(request or "").strip() else {
        "intent": "general_agent",
        "goal": "expand_zero_ai_general_agent_surface",
        "constraints": {},
        "entities": {},
        "claims": [],
        "goals": [],
        "raw": "",
    }

    status = {
        "ok": True,
        "request": str(request or "").strip(),
        "mode": "assess" if str(request or "").strip() else "status",
        "time_utc": _utc_now(),
        "intent": intent,
        "required_subsystems": required,
        "required_subsystem_count": len(required),
        "blocked_subsystem_count": len(blocked),
        "approval_gated_subsystem_count": len(approval_gated),
        "not_ready_subsystem_count": len(not_ready),
        "bounded_execution_ready": executable,
        "general_purpose_ready": executable and general_surface >= 60.0,
        "agentic_ready": executable and int(summary.get("missing_function_count", 0) or 0) == 0,
        "installed_domain_pack_count": installed_packs,
        "active_subsystem_count": int(summary.get("active_subsystem_count", 0) or 0),
        "subsystem_count": int(summary.get("subsystem_count", 0) or 0),
        "active_autonomous_surface_score": general_surface,
        "recommended_mode": (
            "expand_domain" if blocked else
            "stabilize_subsystems" if not_ready else
            "approval_gated_execute" if approval_gated else
            "bounded_execute"
        ),
        "next_actions": _next_actions(required, str(request or "general purpose work")),
        "summary": {
            "general_purpose_ready": executable and general_surface >= 60.0,
            "agentic_ready": executable and int(summary.get("missing_function_count", 0) or 0) == 0,
            "required_subsystem_count": len(required),
            "blocked_subsystem_count": len(blocked),
            "approval_gated_subsystem_count": len(approval_gated),
            "not_ready_subsystem_count": len(not_ready),
            "installed_domain_pack_count": installed_packs,
            "active_autonomous_surface_score": general_surface,
            "recommended_mode": (
                "expand_domain" if blocked else
                "stabilize_subsystems" if not_ready else
                "approval_gated_execute" if approval_gated else
                "bounded_execute"
            ),
        },
    }
    _save(_status_path(cwd), status)
    return status


def general_agent_orchestrator_refresh(cwd: str, request: str = "") -> dict:
    return general_agent_orchestrator_status(cwd, request=request)
