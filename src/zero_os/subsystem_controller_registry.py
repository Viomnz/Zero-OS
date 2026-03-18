from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from zero_os.tool_capability_registry import registry_status
from zero_os.zero_ai_capability_map import zero_ai_capability_map_status


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _assistant_dir(cwd: str) -> Path:
    path = Path(cwd).resolve() / ".zero_os" / "assistant"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _save(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _controller_path(cwd: str) -> Path:
    return _assistant_dir(cwd) / "controller_registry.json"


_SUBSYSTEMS = (
    {
        "key": "observation",
        "label": "Smart workspace monitor",
        "capability_keys": ("smart_workspace_map", "integrity_flow_monitor"),
        "tool_keys": ("local_files", "system_runtime", "recovery"),
        "commands": (
            "zero ai workspace status",
            "zero ai workspace refresh",
            "zero ai flow status",
            "zero ai flow scan",
            "zero ai observe",
        ),
        "notes": "Keeps workspace structure, git drift, contradiction, bug/error, execution, and threat signals visible in one continuous monitoring lane.",
    },
    {
        "key": "reasoning",
        "label": "Reasoning contradiction gate",
        "capability_keys": ("contradiction_gate",),
        "tool_keys": ("system_runtime",),
        "commands": (
            "zero ai contradiction status",
            "zero ai contradiction refresh",
            "zero ai next",
        ),
        "notes": "Runs typed contradiction checks across goal, context, evidence, consequences, and self continuity before output.",
    },
    {
        "key": "pressure",
        "label": "Pressure harness",
        "capability_keys": ("pressure_harness",),
        "tool_keys": ("system_runtime",),
        "commands": (
            "zero ai pressure status",
            "zero ai pressure run",
        ),
        "notes": "Runs isolated survivability pressure checks across approvals, contradiction handling, routing, and task completion.",
    },
    {
        "key": "runtime",
        "label": "Runtime control plane",
        "capability_keys": ("runtime_orchestrator", "background_agent", "runtime_loop"),
        "tool_keys": ("system_runtime", "shell"),
        "commands": (
            "zero ai runtime status",
            "zero ai runtime run",
            "zero ai runtime loop on [interval=<seconds>]",
            "zero ai runtime agent ensure",
            "zero ai runtime agent install",
        ),
        "notes": "Keeps Zero AI alive, scheduled, and able to execute its main orchestration pass.",
    },
    {
        "key": "autonomy",
        "label": "Autonomy manager",
        "capability_keys": ("autonomy_goal_manager",),
        "tool_keys": ("system_runtime",),
        "commands": (
            "zero ai autonomy status",
            "zero ai autonomy goals",
            "zero ai autonomy drain [max=<n>]",
            "zero ai autonomy add [priority=<1-100>] <goal>",
            "zero ai autonomy loop on [interval=<seconds>]",
        ),
        "notes": "Queues and schedules bounded autonomous work.",
    },
    {
        "key": "self_model",
        "label": "Self-model safeguards",
        "capability_keys": ("continuity_guard", "high_risk_self_repair", "identity_core_rewrite"),
        "tool_keys": ("system_runtime", "recovery"),
        "commands": (
            "zero ai continuity governance status",
            "zero ai continuity restore last safe",
            "zero ai workflow self repair",
            "zero ai highest-value steps",
        ),
        "notes": "Protects continuity and forbids unsafe identity-core edits.",
    },
    {
        "key": "evolution",
        "label": "Evolution lane",
        "capability_keys": ("bounded_self_evolution", "guarded_source_evolution", "arbitrary_source_rewrite"),
        "tool_keys": ("local_files", "system_runtime"),
        "commands": (
            "zero ai evolution status",
            "zero ai evolution auto run",
            "zero ai source evolution status",
            "zero ai source evolution auto run",
        ),
        "notes": "Promotes bounded tuning and guarded source evolution with canaries and rollback.",
    },
    {
        "key": "integration",
        "label": "Integration workflows",
        "capability_keys": ("browser_control", "store_installation"),
        "tool_keys": ("browser_automation", "native_store", "api_profiles"),
        "commands": (
            "zero ai workflow browser open url=<url>",
            "zero ai workflow browser act url=<url> action=<open|inspect|click|input>",
            "zero ai workflow install app=<name>",
            "zero ai api profile status",
        ),
        "notes": "Typed browser, store, and API workflows that replace raw unbounded actions.",
    },
    {
        "key": "recovery",
        "label": "Recovery workflows",
        "capability_keys": ("recovery_restore",),
        "tool_keys": ("recovery",),
        "commands": (
            "zero ai workflow recover [snapshot=<id|latest>]",
            "snapshot create",
            "snapshot list",
            "snapshot restore",
        ),
        "notes": "Restores the system from a known-good state instead of improvising high-risk fixes.",
    },
    {
        "key": "platform",
        "label": "Platform-wide control",
        "capability_keys": ("unrestricted_zero_os_control",),
        "tool_keys": ("system_runtime",),
        "commands": (
            "zero ai capability map status",
            "zero ai controller registry status",
            "zero ai control workflows status",
        ),
        "notes": "Unrestricted god-mode control stays forbidden; typed contracts are expanded instead.",
    },
)


def _contract_state(capabilities: list[dict]) -> str:
    levels = {str(item.get("control_level", "")) for item in capabilities}
    if "autonomous" in levels and ({"approval_gated", "forbidden"} & levels):
        return "bounded_autonomous"
    if "autonomous" in levels:
        return "autonomous"
    if "approval_gated" in levels:
        return "approval_gated"
    return "forbidden"


def _current_control_level(capabilities: list[dict]) -> str:
    levels = {str(item.get("control_level", "")) for item in capabilities}
    if "autonomous" in levels:
        return "autonomous"
    if "approval_gated" in levels:
        return "approval_gated"
    return "forbidden"


def _runtime_missing(capabilities: dict[str, dict]) -> tuple[list[str], str]:
    missing: list[str] = []
    if not capabilities.get("runtime_orchestrator", {}).get("active", False):
        missing.append("runtime orchestration baseline")
    if not capabilities.get("background_agent", {}).get("active", False):
        missing.append("background runtime agent")
    if not capabilities.get("runtime_loop", {}).get("active", False):
        missing.append("scheduled runtime loop")
    if "background runtime agent" in missing:
        return missing, "Install and start the runtime agent so Zero AI stays alive between UI sessions."
    if "scheduled runtime loop" in missing:
        return missing, "Enable the runtime loop so the control plane can keep making progress on a timer."
    if "runtime orchestration baseline" in missing:
        return missing, "Run `zero ai runtime run` to create a live runtime baseline before widening autonomy."
    return missing, "Maintain the runtime control plane and keep the agent heartbeat healthy."


def _pressure_missing(capabilities: dict[str, dict]) -> tuple[list[str], str]:
    capability = capabilities.get("pressure_harness", {})
    evidence = dict(capability.get("evidence") or {})
    missing: list[str] = []
    if not capability.get("active", False):
        missing.append("pressure survivability baseline")
    if int(evidence.get("failed_count", 0) or 0) > 0:
        missing.append("pressure failures")
    if "pressure survivability baseline" in missing:
        return missing, "Run `zero ai pressure run` to create a real survivability baseline before calling Zero AI world-class."
    if "pressure failures" in missing:
        return missing, "Fix the top pressure-harness failure before widening autonomy or trust."
    return missing, "Maintain the pressure harness and keep feeding real incidents back into the survivability suite."


def _autonomy_missing(capabilities: dict[str, dict]) -> tuple[list[str], str]:
    capability = capabilities.get("autonomy_goal_manager", {})
    evidence = dict(capability.get("evidence") or {})
    missing: list[str] = []
    if int(evidence.get("blocked_goals", 0) or 0) > 0:
        missing.append("blocked-goal resolution")
    if int(evidence.get("open_goals", 0) or 0) > 0:
        missing.append("goal queue drain")
    if not bool(evidence.get("loop_enabled", False)):
        missing.append("autonomy loop scheduling")
    if "blocked-goal resolution" in missing:
        return missing, "Resolve blocked autonomy goals before expanding Zero AI autonomy."
    if "autonomy loop scheduling" in missing:
        return missing, "Enable the autonomy loop so the goal manager can make bounded progress without manual polling."
    if "goal queue drain" in missing:
        return missing, "Shrink or complete the open goal queue so the autonomy manager can return to a stable idle state."
    return missing, "Maintain bounded autonomous execution and keep the goal queue clean."


def _self_model_missing(capabilities: dict[str, dict]) -> tuple[list[str], str]:
    missing: list[str] = []
    if not capabilities.get("continuity_guard", {}).get("active", False):
        missing.append("continuity restoration")
    if not capabilities.get("high_risk_self_repair", {}).get("active", False):
        missing.append("canary-backed self-repair workflow")
    if "continuity restoration" in missing:
        return missing, "Restore continuity and clear contradiction signals before any broader Zero AI upgrade."
    if "canary-backed self-repair workflow" in missing:
        return missing, "Finish the safe self-repair workflow so repair actions always verify and roll back cleanly."
    return missing, "Keep identity continuity guarded and continue forbidding identity-core rewrites."


def _reasoning_missing(capabilities: dict[str, dict]) -> tuple[list[str], str]:
    capability = capabilities.get("contradiction_gate", {})
    evidence = dict(capability.get("evidence") or {})
    missing: list[str] = []
    if not capability.get("active", False):
        missing.append("contradiction gate enablement")
    if bool(evidence.get("continuity_has_contradiction", False)):
        missing.append("continuity stabilization")
    if "continuity stabilization" in missing:
        return missing, "Resolve active self contradiction so the contradiction gate can trust the current self model."
    if "contradiction gate enablement" in missing:
        return missing, "Build the contradiction engine and make it the gate before output."
    return missing, "Maintain the contradiction gate and extend typed reasoning checks across more subsystems."


def _observation_missing(capabilities: dict[str, dict]) -> tuple[list[str], str]:
    workspace_capability = capabilities.get("smart_workspace_map", {})
    workspace_evidence = dict(workspace_capability.get("evidence") or {})
    capability = capabilities.get("integrity_flow_monitor", {})
    evidence = dict(capability.get("evidence") or {})
    missing: list[str] = []
    if not workspace_capability.get("active", False):
        missing.append("smart workspace activation")
    if not bool(workspace_evidence.get("indexed", False)):
        missing.append("workspace intelligence baseline")
    if not capability.get("active", False):
        missing.append("flow monitor activation")
    if not bool(evidence.get("source_scan_available", False)):
        missing.append("full integrity scan baseline")
    if "smart workspace activation" in missing:
        return missing, "Expose the smart workspace lane so Zero AI can understand structure, drift, and risk together."
    if "workspace intelligence baseline" in missing:
        return missing, "Run `zero ai workspace refresh` to build a searchable smart workspace map before broader edits."
    if "flow monitor activation" in missing:
        return missing, "Expose the smooth flow monitor so Zero AI can detect contradictions, bugs, errors, and virus signals together."
    if "full integrity scan baseline" in missing:
        return missing, "Run `zero ai flow scan` to establish a full integrity baseline across contradiction, source, execution, and threat lanes."
    return missing, "Maintain the smart workspace and unified flow monitor so Zero AI keeps structure, contradictions, bugs, errors, and threat signals visible in one lane."


def _evolution_missing(capabilities: dict[str, dict]) -> tuple[list[str], str]:
    missing: list[str] = []
    if not capabilities.get("bounded_self_evolution", {}).get("active", False):
        missing.append("bounded self-evolution loop")
    if not capabilities.get("guarded_source_evolution", {}).get("active", False):
        missing.append("guarded source-evolution lane")
    if "guarded source-evolution lane" in missing:
        return missing, "Expand guarded source evolution into a sandboxed patch lane for selected non-identity modules."
    if "bounded self-evolution loop" in missing:
        return missing, "Finish the canary-backed self-evolution loop before promoting more autonomous tuning."
    return missing, "Maintain bounded evolution and keep arbitrary source rewrites forbidden."


def _integration_missing(capabilities: dict[str, dict], tools: dict[str, dict]) -> tuple[list[str], str]:
    missing: list[str] = []
    if not capabilities.get("browser_control", {}).get("active", False):
        missing.append("typed browser workflow promotion")
    if not capabilities.get("store_installation", {}).get("active", False):
        missing.append("store install target package")
    if tools.get("api_profiles", {}).get("gaps"):
        missing.append("reusable API profile")
    if "store install target package" in missing:
        return missing, "Publish or register at least one app package so the autonomous install workflow has a real target."
    if "typed browser workflow promotion" in missing:
        return missing, "Promote an allowlisted browser workflow so integration actions stay inside typed contracts."
    if "reusable API profile" in missing:
        return missing, "Configure an API profile so external integrations can run through typed connectors."
    return missing, "Maintain typed integration workflows and keep raw high-risk actions gated."


def _recovery_missing(capabilities: dict[str, dict]) -> tuple[list[str], str]:
    missing: list[str] = []
    if not capabilities.get("recovery_restore", {}).get("active", False):
        missing.append("baseline recovery snapshot")
    if missing:
        return missing, "Create a baseline recovery snapshot so Zero AI can restore from a known-good point immediately."
    return missing, "Maintain fresh snapshots so recovery stays fast and reversible."


def _platform_missing(capabilities: dict[str, dict]) -> tuple[list[str], str]:
    current = capabilities.get("unrestricted_zero_os_control", {})
    if str(current.get("control_level", "")) == "forbidden":
        return [], "Keep unrestricted platform-wide control forbidden and expand typed safe workflows instead of adding a god-mode lane."
    return [], "Maintain explicit typed contracts for platform-wide control."


def _missing_functions_for(
    subsystem_key: str,
    capabilities: dict[str, dict],
    tools: dict[str, dict],
) -> tuple[list[str], str]:
    if subsystem_key == "observation":
        return _observation_missing(capabilities)
    if subsystem_key == "reasoning":
        return _reasoning_missing(capabilities)
    if subsystem_key == "pressure":
        return _pressure_missing(capabilities)
    if subsystem_key == "runtime":
        return _runtime_missing(capabilities)
    if subsystem_key == "autonomy":
        return _autonomy_missing(capabilities)
    if subsystem_key == "self_model":
        return _self_model_missing(capabilities)
    if subsystem_key == "evolution":
        return _evolution_missing(capabilities)
    if subsystem_key == "integration":
        return _integration_missing(capabilities, tools)
    if subsystem_key == "recovery":
        return _recovery_missing(capabilities)
    return _platform_missing(capabilities)


def controller_registry_status(cwd: str) -> dict:
    capability_map = zero_ai_capability_map_status(cwd)
    tool_status = registry_status(cwd)
    tools = dict(tool_status.get("tools") or {})
    capability_by_key = {
        str(item.get("key", "")): dict(item)
        for item in capability_map.get("capabilities", [])
    }

    subsystems: list[dict] = []
    highest_value_steps: list[str] = []
    missing_functions: list[str] = []
    for definition in _SUBSYSTEMS:
        capabilities = [
            capability_by_key[key]
            for key in definition["capability_keys"]
            if key in capability_by_key
        ]
        capability_lookup = {item["key"]: item for item in capabilities}
        missing, next_step = _missing_functions_for(definition["key"], capability_lookup, tools)
        subsystem = {
            "key": definition["key"],
            "label": definition["label"],
            "control_level": _current_control_level(capabilities),
            "contract_state": _contract_state(capabilities),
            "active": any(bool(item.get("active", False)) for item in capabilities),
            "ready": all(bool(item.get("ready", False)) for item in capabilities) if capabilities else False,
            "commands": list(definition["commands"]),
            "tools": [
                {"key": key, **dict(tools.get(key) or {})}
                for key in definition["tool_keys"]
                if key in tools
            ],
            "capabilities": [
                {
                    "key": item["key"],
                    "label": item.get("label", ""),
                    "control_level": item.get("control_level", ""),
                    "active": bool(item.get("active", False)),
                    "ready": bool(item.get("ready", False)),
                }
                for item in capabilities
            ],
            "blocking_capabilities": [
                {
                    "key": item["key"],
                    "label": item.get("label", ""),
                    "control_level": item.get("control_level", ""),
                }
                for item in capabilities
                if item.get("control_level") != "autonomous"
            ],
            "missing_functions": missing,
            "highest_value_step": next_step,
            "notes": definition["notes"],
        }
        subsystems.append(subsystem)
        missing_functions.extend(missing)
        if missing or definition["key"] in {"reasoning", "platform"}:
            highest_value_steps.append(next_step)

    path = _controller_path(cwd)
    status = {
        "ok": True,
        "time_utc": _utc_now(),
        "path": str(path),
        "summary": {
            "subsystem_count": len(subsystems),
            "autonomous_subsystem_count": sum(1 for item in subsystems if item["control_level"] == "autonomous"),
            "approval_gated_subsystem_count": sum(1 for item in subsystems if item["control_level"] == "approval_gated"),
            "forbidden_subsystem_count": sum(1 for item in subsystems if item["control_level"] == "forbidden"),
            "active_subsystem_count": sum(1 for item in subsystems if item["active"]),
            "missing_function_count": len(missing_functions),
        },
        "tool_summary": dict(tool_status.get("summary") or {}),
        "subsystems": subsystems,
        "missing_functions": missing_functions,
        "highest_value_steps": highest_value_steps[:6],
        "next_priority": highest_value_steps[:3],
    }
    _save(path, status)
    return status


def controller_registry_refresh(cwd: str) -> dict:
    return controller_registry_status(cwd)
