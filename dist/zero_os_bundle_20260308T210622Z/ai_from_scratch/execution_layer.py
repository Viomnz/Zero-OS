from __future__ import annotations

import json
from pathlib import Path

try:
    from ai_from_scratch.communication_interface import execution_interface
    from ai_from_scratch.core_rule_layer import verify_core_rules
except ModuleNotFoundError:
    from communication_interface import execution_interface
    from core_rule_layer import verify_core_rules


def _runtime(cwd: str) -> Path:
    p = Path(cwd).resolve() / ".zero_os" / "runtime"
    p.mkdir(parents=True, exist_ok=True)
    return p


def execute_decision(
    cwd: str,
    action_text: str,
    channel: str,
    context: dict,
    resources: dict | None = None,
    stability: dict | None = None,
) -> dict:
    core = verify_core_rules(cwd)
    resources = resources or {"decision": "approve"}
    stability = stability or {"stable": True}

    prechecks = {
        "rule_compliance": bool(core.get("ok", False)),
        "resource_available": str(resources.get("decision", "approve")) == "approve",
        "system_stability": bool(stability.get("stable", True)),
    }
    if not all(prechecks.values()):
        out = {
            "ok": False,
            "executed": False,
            "reason": "precheck_failed",
            "prechecks": prechecks,
            "dispatch": {"allowed": False, "safe_output": ""},
            "state_update": {"applied": False},
        }
        (_runtime(cwd) / "execution_layer.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
        return out

    # Execution sequence: dispatch -> verify route -> update state snapshot
    dispatch = execution_interface(action_text, channel)
    executed = bool(dispatch.get("allowed", False))
    state_update = {
        "applied": executed,
        "channel": channel,
        "priority_mode": str(context.get("reasoning_parameters", {}).get("priority_mode", "normal")),
        "output_length": len(str(dispatch.get("safe_output", ""))),
    }

    out = {
        "ok": True,
        "executed": executed,
        "reason": "executed" if executed else "dispatch_blocked",
        "prechecks": prechecks,
        "dispatch": dispatch,
        "state_update": state_update,
    }
    (_runtime(cwd) / "execution_layer.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    return out

