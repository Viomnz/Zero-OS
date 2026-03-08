from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _policy_path(cwd: str) -> Path:
    path = Path(cwd).resolve() / ".zero_os" / "assistant" / "agent_policy.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(
            json.dumps(
                {
                    "allow": ["web_verify", "web_fetch", "system_status", "tool_registry", "store_status", "api_request", "api_workflow"],
                    "approval_required": ["browser_action", "store_install", "recover", "self_repair"],
                    "deny": [],
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
    return json.loads(_policy_path(cwd).read_text(encoding="utf-8", errors="replace"))


def classify_action(cwd: str, action_kind: str) -> dict:
    policy = policy_status(cwd)
    kind = action_kind.strip()
    if kind in set(policy.get("deny", [])):
        return {"decision": "deny", "action_kind": kind}
    if kind in set(policy.get("approval_required", [])):
        return {"decision": "approval_required", "action_kind": kind}
    return {"decision": "allow", "action_kind": kind}


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
