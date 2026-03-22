from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


_DEFAULT_ACTION_TIERS = {
    "observe": "safe_auto",
    "system_status": "safe_auto",
    "tool_registry": "safe_auto",
    "browser_status": "safe_auto",
    "browser_dom_inspect": "safe_auto",
    "web_verify": "safe_auto",
    "web_fetch": "safe_auto",
    "browser_open": "safe_auto",
    "store_status": "safe_auto",
    "api_request": "safe_auto",
    "api_workflow": "safe_auto",
    "browser_action": "approval_required",
    "store_install": "approval_required",
    "recover": "approval_required",
    "self_repair": "approval_required",
}

_TIER_SPECS = {
    "observe_only": {"decision": "observe_only", "description": "Allowed only as read-only observation or status gathering.", "requires_rollback": False, "requires_approval": False},
    "safe_auto": {"decision": "allow", "description": "May run automatically without approval.", "requires_rollback": False, "requires_approval": False},
    "guarded_auto": {"decision": "allow", "description": "May run automatically only if autonomy and rollback checks pass.", "requires_rollback": True, "requires_approval": False},
    "approval_required": {"decision": "approval_required", "description": "Requires explicit user approval before execution.", "requires_rollback": True, "requires_approval": True},
    "forbidden": {"decision": "deny", "description": "Blocked by policy.", "requires_rollback": False, "requires_approval": False},
}


def _policy_path(cwd: str) -> Path:
    path = Path(cwd).resolve() / ".zero_os" / "assistant" / "agent_policy.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(
            json.dumps(
                {
                    "allow": sorted([kind for kind, tier in _DEFAULT_ACTION_TIERS.items() if tier in {"safe_auto", "guarded_auto"}]),
                    "approval_required": sorted([kind for kind, tier in _DEFAULT_ACTION_TIERS.items() if tier == "approval_required"]),
                    "deny": [],
                    "actions": dict(_DEFAULT_ACTION_TIERS),
                    "tiers": dict(_TIER_SPECS),
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
    return path


def _audit_path(cwd: str) -> Path:
    path = Path(cwd).resolve() / ".zero_os" / "assistant" / "agent_audit.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def policy_status(cwd: str) -> dict:
    policy = json.loads(_policy_path(cwd).read_text(encoding="utf-8", errors="replace"))
    actions = dict(_DEFAULT_ACTION_TIERS)
    for kind in policy.get("allow", []):
        actions[str(kind)] = "safe_auto"
    for kind in policy.get("approval_required", []):
        actions[str(kind)] = "approval_required"
    for kind in policy.get("deny", []):
        actions[str(kind)] = "forbidden"
    actions.update({str(key): str(value) for key, value in dict(policy.get("actions") or {}).items() if str(value)})
    policy["actions"] = actions
    policy["tiers"] = {**_TIER_SPECS, **dict(policy.get("tiers") or {})}
    policy["allow"] = sorted([kind for kind, tier in actions.items() if tier in {"safe_auto", "guarded_auto"}])
    policy["approval_required"] = sorted([kind for kind, tier in actions.items() if tier == "approval_required"])
    policy["deny"] = sorted([kind for kind, tier in actions.items() if tier == "forbidden"])
    policy["tier_counts"] = {tier: sum(1 for value in actions.values() if value == tier) for tier in policy["tiers"].keys()}
    _policy_path(cwd).write_text(json.dumps(policy, indent=2) + "\n", encoding="utf-8")
    return policy


def set_action_tier(cwd: str, action_kind: str, tier: str) -> dict:
    normalized_kind = str(action_kind or "").strip()
    normalized_tier = str(tier or "").strip().lower()
    if not normalized_kind:
        return {"ok": False, "reason": "empty_action_kind"}
    if normalized_tier not in _TIER_SPECS:
        return {"ok": False, "reason": f"unknown_tier:{normalized_tier}", "allowed_tiers": sorted(_TIER_SPECS.keys())}
    policy = policy_status(cwd)
    actions = dict(policy.get("actions") or {})
    actions[normalized_kind] = normalized_tier
    policy["actions"] = actions
    policy["allow"] = sorted([kind for kind, value in actions.items() if value in {"safe_auto", "guarded_auto"}])
    policy["approval_required"] = sorted([kind for kind, value in actions.items() if value == "approval_required"])
    policy["deny"] = sorted([kind for kind, value in actions.items() if value == "forbidden"])
    policy["updated_utc"] = _utc_now()
    _policy_path(cwd).write_text(json.dumps(policy, indent=2) + "\n", encoding="utf-8")
    return {"ok": True, "action_kind": normalized_kind, "tier": normalized_tier, "policy": policy_status(cwd)}


def classify_action(cwd: str, action_kind: str) -> dict:
    policy = policy_status(cwd)
    kind = action_kind.strip()
    tier = str((policy.get("actions") or {}).get(kind) or "safe_auto")
    spec = dict((policy.get("tiers") or {}).get(tier) or _TIER_SPECS["safe_auto"])
    return {
        "decision": str(spec.get("decision", "allow")),
        "tier": tier,
        "action_kind": kind,
        "requires_rollback": bool(spec.get("requires_rollback", False)),
        "requires_approval": bool(spec.get("requires_approval", False)),
        "description": str(spec.get("description", "")),
    }


def audit_event(cwd: str, action_kind: str, state: str, payload: dict | None = None) -> dict:
    record = {
        "time_utc": _utc_now(),
        "action_kind": action_kind,
        "state": state,
        "payload": payload or {},
    }
    with _audit_path(cwd).open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")
    return {"ok": True, "record": record}
