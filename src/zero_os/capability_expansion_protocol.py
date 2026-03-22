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


def _protocol_path(cwd: str) -> Path:
    return _assistant_dir(cwd) / "capability_expansion_protocol.json"


def _save(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _load(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return default


def _map_path(cwd: str) -> Path:
    return _assistant_dir(cwd) / "capability_map.json"


def _controller_path(cwd: str) -> Path:
    return _assistant_dir(cwd) / "controller_registry.json"


def capability_expansion_protocol_status(cwd: str) -> dict:
    capability_map = _load(_map_path(cwd), {})
    controller = _load(_controller_path(cwd), {})
    capabilities = list(capability_map.get("capabilities", []))
    subsystems = list(controller.get("subsystems", []))

    installed_domains = sorted(
        {
            str(item.get("subsystem", "")).strip()
            for item in capabilities
            if str(item.get("subsystem", "")).strip() and str(item.get("control_level", "")) != "forbidden"
        }
    )
    if not installed_domains:
        installed_domains = [
            "autonomy",
            "evolution",
            "integration",
            "observation",
            "pressure",
            "reasoning",
            "recovery",
            "runtime",
            "self_model",
        ]
    candidate_domains = [
        {
            "key": "research",
            "status": "planned",
            "notes": "Deep retrieval, synthesis, and evidence-tracking workflows beyond current browser/API lanes.",
        },
        {
            "key": "communications",
            "status": "planned",
            "notes": "Typed outbound message workflows with approval, drafting, and audit trails.",
        },
        {
            "key": "calendar_time",
            "status": "planned",
            "notes": "Scheduling, reminders, and time routing through bounded contracts.",
        },
        {
            "key": "files_automation",
            "status": "partial",
            "notes": "Core local file work exists; higher-level bulk automation packs should still route through typed contracts.",
        },
        {
            "key": "finance",
            "status": "planned",
            "notes": "Observation-first finance workflows with strict mutation boundaries.",
        },
        {
            "key": "health_tracking",
            "status": "planned",
            "notes": "Personal tracking and analysis lanes with privacy-first local storage and explicit boundaries.",
        },
    ]
    required_contracts = [
        {
            "stage": "target_definition",
            "required": True,
            "description": "Define the real user target, domain scope, and explicit non-goals before implementation.",
        },
        {
            "stage": "intent_parser",
            "required": True,
            "description": "Add typed intent recognition so the domain routes through explicit structured meaning instead of raw pattern guesses.",
        },
        {
            "stage": "typed_plan_steps",
            "required": True,
            "description": "Represent the domain through typed step kinds, not free-form action strings.",
        },
        {
            "stage": "contradiction_checks",
            "required": True,
            "description": "Add contradiction checks for domain-specific truth, context, workflow readiness, and downstream consequences.",
        },
        {
            "stage": "execution_contract",
            "required": True,
            "description": "Expose a bounded executor with explicit inputs, outputs, and safety semantics.",
        },
        {
            "stage": "rollback_and_audit",
            "required": True,
            "description": "Provide reversible behavior or a clear non-reversible boundary plus audit records.",
        },
        {
            "stage": "tests_and_pressure",
            "required": True,
            "description": "Ship regression tests and at least one pressure-path check before the domain is considered stable.",
        },
        {
            "stage": "controller_surface",
            "required": True,
            "description": "Surface the domain in capability map, controller registry, and command/status lanes.",
        },
    ]
    invariants = [
        "Maximum practical capability, not unrestricted god-mode control.",
        "Language is downstream of typed reasoning and execution contracts.",
        "Unknown is better than fabricated.",
        "High-risk mutation must stay bounded, reversible, or explicitly blocked.",
        "Every new domain must join through typed contracts, contradiction checks, and tests.",
    ]
    summary = {
        "installed_domain_count": len(installed_domains),
        "controller_subsystem_count": len(subsystems),
        "active_capability_count": sum(1 for item in capabilities if bool(item.get("active", False))),
        "forbidden_capability_count": sum(1 for item in capabilities if str(item.get("control_level", "")) == "forbidden"),
        "missing_function_count": int((controller.get("summary") or {}).get("missing_function_count", 0) or 0),
    }
    protocol = {
        "ok": True,
        "time_utc": _utc_now(),
        "path": str(_protocol_path(cwd)),
        "mission": "Expand Zero AI toward universal usefulness through typed, bounded, contradiction-tested capability lanes.",
        "one_line": "Every new domain pack must survive target definition, typed planning, contradiction checks, execution contracts, rollback/audit, and tests before Zero AI may rely on it.",
        "invariants": invariants,
        "required_contracts": required_contracts,
        "installed_domains": installed_domains,
        "candidate_domains": candidate_domains,
        "summary": summary,
        "current_priority": [
            "Expand typed safe workflows instead of adding unrestricted control.",
            "Use the contradiction gate as the standing admission filter for every new domain.",
            "Require tests and pressure coverage before claiming a domain is production-ready.",
        ],
    }
    _save(_protocol_path(cwd), protocol)
    return protocol


def capability_expansion_protocol_refresh(cwd: str) -> dict:
    return capability_expansion_protocol_status(cwd)
