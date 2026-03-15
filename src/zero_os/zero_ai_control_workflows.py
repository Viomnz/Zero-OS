from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _assistant_dir(cwd: str) -> Path:
    path = Path(cwd).resolve() / ".zero_os" / "assistant"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _state_path(cwd: str) -> Path:
    return _assistant_dir(cwd) / "control_workflows.json"


def _history_path(cwd: str) -> Path:
    return _assistant_dir(cwd) / "control_workflow_runs.jsonl"


def _load_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return dict(default)
    try:
        payload = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return dict(default)
    if not isinstance(payload, dict):
        return dict(default)
    merged = dict(default)
    merged.update(payload)
    return merged


def _save_json(path: Path, payload: dict[str, Any]) -> None:
    payload["updated_utc"] = _utc_now()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _append_history(cwd: str, payload: dict[str, Any]) -> None:
    with _history_path(cwd).open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")


def _history_tail(cwd: str, limit: int = 12) -> list[dict[str, Any]]:
    path = _history_path(cwd)
    if not path.exists():
        return []
    rows = [line.strip() for line in path.read_text(encoding="utf-8", errors="replace").splitlines() if line.strip()]
    out: list[dict[str, Any]] = []
    for row in rows[-limit:]:
        try:
            payload = json.loads(row)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            out.append(payload)
    return out


def _lane_defaults() -> dict[str, dict[str, Any]]:
    return {
        "browser": {
            "enabled": True,
            "mode": "canary_backed",
            "allow_domains": ["github.com", "localhost", "127.0.0.1", "example.org"],
            "allowed_actions": ["open", "inspect", "click", "input"],
            "success_count": 0,
            "failure_count": 0,
            "last_run": {},
            "recent_runs": [],
        },
        "store_install": {
            "enabled": True,
            "mode": "canary_backed",
            "default_tier": "free",
            "canary_email_domain": "zero-ai.local",
            "success_count": 0,
            "failure_count": 0,
            "last_run": {},
            "recent_runs": [],
        },
        "recovery": {
            "enabled": True,
            "mode": "canary_backed",
            "default_snapshot": "latest",
            "success_count": 0,
            "failure_count": 0,
            "last_run": {},
            "recent_runs": [],
        },
        "self_repair": {
            "enabled": True,
            "mode": "canary_backed",
            "minimum_readiness_floor": 90,
            "success_count": 0,
            "failure_count": 0,
            "last_run": {},
            "recent_runs": [],
        },
    }


def _state_default() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "lanes": _lane_defaults(),
        "updated_utc": _utc_now(),
    }


def _load_state(cwd: str) -> dict[str, Any]:
    state = _load_json(_state_path(cwd), _state_default())
    state.setdefault("schema_version", 1)
    lanes = dict(state.get("lanes") or {})
    defaults = _lane_defaults()
    for lane_name, lane_default in defaults.items():
        lane = dict(lanes.get(lane_name) or {})
        for key, value in lane_default.items():
            lane.setdefault(key, value)
        lane["recent_runs"] = list(lane.get("recent_runs") or [])
        lane["last_run"] = dict(lane.get("last_run") or {})
        lanes[lane_name] = lane
    state["lanes"] = lanes
    return state


def _save_state(cwd: str, state: dict[str, Any]) -> dict[str, Any]:
    _save_json(_state_path(cwd), state)
    return state


def _lane_state(cwd: str, lane_name: str) -> tuple[dict[str, Any], dict[str, Any]]:
    state = _load_state(cwd)
    lane = dict((state.get("lanes") or {}).get(lane_name) or {})
    return state, lane


def _record_lane_run(
    cwd: str,
    lane_name: str,
    *,
    ok: bool,
    summary: str,
    canary: dict[str, Any],
    result: dict[str, Any],
    request: dict[str, Any] | None = None,
) -> dict[str, Any]:
    from zero_os.agent_permission_policy import audit_event

    state = _load_state(cwd)
    lane = dict(state["lanes"][lane_name])
    record = {
        "time_utc": _utc_now(),
        "lane": lane_name,
        "ok": bool(ok),
        "summary": summary,
        "request": dict(request or {}),
        "canary": dict(canary or {}),
        "result": dict(result or {}),
    }
    lane["last_run"] = record
    lane["success_count"] = int(lane.get("success_count", 0)) + (1 if ok else 0)
    lane["failure_count"] = int(lane.get("failure_count", 0)) + (0 if ok else 1)
    recent = list(lane.get("recent_runs") or [])
    recent.append(
        {
            "time_utc": record["time_utc"],
            "ok": bool(ok),
            "summary": summary,
        }
    )
    lane["recent_runs"] = recent[-12:]
    state["lanes"][lane_name] = lane
    _save_state(cwd, state)
    _append_history(cwd, record)
    audit_event(cwd, f"workflow_{lane_name}", "success" if ok else "failed", {"summary": summary, "canary_ok": bool(canary.get("ok", False))})
    return record


def _normalize_domain(url: str) -> tuple[str, str]:
    parsed = urlparse(url.strip())
    return parsed.scheme.lower(), (parsed.hostname or "").lower()


def _browser_url_allowed(url: str, allow_domains: list[str]) -> tuple[bool, str]:
    scheme, host = _normalize_domain(url)
    if scheme == "file":
        return True, "local_file"
    if scheme not in {"http", "https"}:
        return False, f"unsupported scheme: {scheme or 'none'}"
    if not host:
        return False, "missing host"
    normalized = [item.strip().lower() for item in allow_domains if item.strip()]
    for allowed in normalized:
        if host == allowed or host.endswith("." + allowed):
            return True, host
    return False, f"domain not allowlisted: {host}"


def _browser_lane_status(cwd: str, lane: dict[str, Any]) -> dict[str, Any]:
    from zero_os.agent_permission_policy import classify_action
    from zero_os.browser_dom_automation import status as browser_dom_status
    from zero_os.browser_session_connector import browser_session_status

    session = browser_session_status(cwd)
    dom = browser_dom_status(cwd)
    return {
        "enabled": bool(lane.get("enabled", False)),
        "mode": str(lane.get("mode", "canary_backed")),
        "ready": bool(lane.get("enabled", False)) and bool(lane.get("allow_domains")) and bool(lane.get("allowed_actions")),
        "active": bool(lane.get("enabled", False)),
        "control_level": "autonomous" if bool(lane.get("enabled", False)) else "approval_gated",
        "raw_action_policy": classify_action(cwd, "browser_action"),
        "allow_domains": list(lane.get("allow_domains", [])),
        "allowed_actions": list(lane.get("allowed_actions", [])),
        "session_last_opened": str(session.get("last_opened", "")),
        "session_tab_count": len(session.get("tabs", [])),
        "dom_page_count": len((dom.get("pages") or {}).keys()),
        "last_run": dict(lane.get("last_run") or {}),
        "recent_runs": list(lane.get("recent_runs") or []),
    }


def _store_lane_status(cwd: str, lane: dict[str, Any]) -> dict[str, Any]:
    from zero_os.agent_permission_policy import classify_action
    from zero_os.app_store_universal import list_packages

    packages = list_packages(cwd)
    apps = list(packages.get("apps", []))
    available_apps = [str(app.get("name", "")) for app in apps if str(app.get("name", "")).strip()]
    return {
        "enabled": bool(lane.get("enabled", False)),
        "mode": str(lane.get("mode", "canary_backed")),
        "ready": bool(lane.get("enabled", False)),
        "active": bool(lane.get("enabled", False)) and len(available_apps) > 0,
        "control_level": "autonomous" if bool(lane.get("enabled", False)) else "approval_gated",
        "raw_action_policy": classify_action(cwd, "store_install"),
        "registry_total": int(packages.get("total", 0) or 0),
        "available_apps": available_apps[:12],
        "last_run": dict(lane.get("last_run") or {}),
        "recent_runs": list(lane.get("recent_runs") or []),
    }


def _recovery_lane_status(cwd: str, lane: dict[str, Any]) -> dict[str, Any]:
    from zero_os.agent_permission_policy import classify_action
    from zero_os.recovery import zero_ai_backup_status

    backup = zero_ai_backup_status(cwd)
    return {
        "enabled": bool(lane.get("enabled", False)),
        "mode": str(lane.get("mode", "canary_backed")),
        "ready": bool(lane.get("enabled", False)),
        "active": bool(lane.get("enabled", False)),
        "control_level": "autonomous" if bool(lane.get("enabled", False)) else "approval_gated",
        "raw_action_policy": classify_action(cwd, "recover"),
        "snapshot_count": int(backup.get("snapshot_count", 0) or 0),
        "latest_snapshot": str(backup.get("latest_snapshot", "")),
        "last_run": dict(lane.get("last_run") or {}),
        "recent_runs": list(lane.get("recent_runs") or []),
    }


def _self_repair_lane_status(cwd: str, lane: dict[str, Any]) -> dict[str, Any]:
    from zero_os.agent_permission_policy import classify_action
    from zero_os.recovery import zero_ai_backup_status
    from zero_os.readiness import os_readiness
    from zero_os.self_continuity import zero_ai_self_continuity_status
    from zero_os.self_repair import self_repair_status

    backup = zero_ai_backup_status(cwd)
    continuity = zero_ai_self_continuity_status(cwd)
    repair = self_repair_status(cwd)
    continuity_block = dict(continuity.get("continuity") or {})
    contradiction_block = dict(continuity.get("contradiction_detection") or {})
    return {
        "enabled": bool(lane.get("enabled", False)),
        "mode": str(lane.get("mode", "canary_backed")),
        "ready": bool(lane.get("enabled", False)),
        "active": bool(lane.get("enabled", False)),
        "control_level": "autonomous" if bool(lane.get("enabled", False)) else "approval_gated",
        "raw_action_policy": classify_action(cwd, "self_repair"),
        "snapshot_count": int(backup.get("snapshot_count", 0) or 0),
        "latest_snapshot": str(backup.get("latest_snapshot", "")),
        "readiness_score": int((os_readiness(cwd) or {}).get("score", 0) or 0),
        "same_system": bool(continuity_block.get("same_system", False)),
        "has_contradiction": bool(contradiction_block.get("has_contradiction", False)),
        "repair_state": repair,
        "last_run": dict(lane.get("last_run") or {}),
        "recent_runs": list(lane.get("recent_runs") or []),
    }


def zero_ai_control_workflows_status(cwd: str) -> dict[str, Any]:
    state = _load_state(cwd)
    browser_lane = _browser_lane_status(cwd, dict(state["lanes"]["browser"]))
    store_lane = _store_lane_status(cwd, dict(state["lanes"]["store_install"]))
    recovery_lane = _recovery_lane_status(cwd, dict(state["lanes"]["recovery"]))
    self_repair_lane = _self_repair_lane_status(cwd, dict(state["lanes"]["self_repair"]))

    lanes = {
        "browser": browser_lane,
        "store_install": store_lane,
        "recovery": recovery_lane,
        "self_repair": self_repair_lane,
    }

    total = len(lanes)
    autonomous = sum(1 for lane in lanes.values() if lane["control_level"] == "autonomous")
    active = sum(1 for lane in lanes.values() if lane["active"])
    ready = sum(1 for lane in lanes.values() if lane["ready"])

    highest_value_steps: list[str] = []
    if not store_lane["active"]:
        highest_value_steps.append("Publish or register at least one app package so the autonomous store-install workflow has a real target.")
    if int(recovery_lane.get("snapshot_count", 0) or 0) == 0:
        highest_value_steps.append("Create a baseline recovery snapshot so the autonomous recovery workflow can restore from a known-good point immediately.")
    highest_value_steps.append("Expand the typed workflow contract into more subsystems so every safe Zero OS control lane has the same canary-backed autonomy model.")

    status = {
        "ok": True,
        "path": str(_state_path(cwd)),
        "history_path": str(_history_path(cwd)),
        "summary": {
            "lane_count": total,
            "autonomous_count": autonomous,
            "ready_count": ready,
            "active_count": active,
        },
        "lanes": lanes,
        "recent_runs": _history_tail(cwd, limit=10),
        "highest_value_steps": highest_value_steps,
    }
    _save_state(cwd, state)
    return status


def zero_ai_control_workflows_refresh(cwd: str) -> dict[str, Any]:
    return zero_ai_control_workflows_status(cwd)


def zero_ai_control_workflow_browser_open(cwd: str, url: str) -> dict[str, Any]:
    from zero_os.browser_dom_automation import inspect_page
    from zero_os.browser_session_connector import browser_session_open

    state, lane = _lane_state(cwd, "browser")
    allowed, detail = _browser_url_allowed(url, list(lane.get("allow_domains", [])))
    canary = {
        "ok": bool(allowed),
        "checks": {
            "lane_enabled": bool(lane.get("enabled", False)),
            "allowlisted_target": bool(allowed),
        },
        "detail": detail,
    }
    if not bool(lane.get("enabled", False)):
        canary["ok"] = False
        canary["detail"] = "browser workflow disabled"
    if not canary["ok"]:
        result = {"ok": False, "reason": canary["detail"], "url": url}
        _record_lane_run(cwd, "browser", ok=False, summary=str(result["reason"]), canary=canary, result=result, request={"url": url, "workflow": "open"})
        return {"ok": False, "workflow": "browser_open", "canary": canary, "result": result, "status": zero_ai_control_workflows_status(cwd)}

    inspect = inspect_page(cwd, url)
    opened = browser_session_open(cwd, url)
    canary["inspect"] = inspect
    canary["ok"] = bool(inspect.get("ok", False)) and bool(opened.get("ok", False))
    result = {
        "ok": canary["ok"] and bool(opened.get("opened", False) or opened.get("ok", False)),
        "url": url,
        "inspect": inspect,
        "session": opened,
        "summary": "browser workflow opened an allowlisted target after DOM canary inspection",
    }
    _record_lane_run(cwd, "browser", ok=bool(result["ok"]), summary=str(result["summary"]), canary=canary, result=result, request={"url": url, "workflow": "open"})
    return {"ok": bool(result["ok"]), "workflow": "browser_open", "canary": canary, "result": result, "status": zero_ai_control_workflows_status(cwd)}


def zero_ai_control_workflow_browser_act(cwd: str, url: str, action: str, selector: str = "", value: str = "") -> dict[str, Any]:
    from zero_os.browser_dom_automation import act as browser_dom_act, inspect_page

    state, lane = _lane_state(cwd, "browser")
    normalized_action = action.strip().lower()
    allowed, detail = _browser_url_allowed(url, list(lane.get("allow_domains", [])))
    action_allowed = normalized_action in set(str(item).strip().lower() for item in lane.get("allowed_actions", []))
    selector_required = normalized_action in {"click", "input"}
    canary = {
        "ok": bool(lane.get("enabled", False)) and bool(allowed) and bool(action_allowed) and (not selector_required or bool(selector.strip())),
        "checks": {
            "lane_enabled": bool(lane.get("enabled", False)),
            "allowlisted_target": bool(allowed),
            "action_allowed": bool(action_allowed),
            "selector_present": (not selector_required) or bool(selector.strip()),
        },
        "detail": detail if not allowed else "",
    }
    if not canary["ok"]:
        reason = canary["detail"] or "browser workflow canary rejected the requested action"
        result = {"ok": False, "reason": reason, "url": url, "action": normalized_action}
        _record_lane_run(
            cwd,
            "browser",
            ok=False,
            summary=reason,
            canary=canary,
            result=result,
            request={"url": url, "workflow": "act", "action": normalized_action, "selector": selector, "value": value},
        )
        return {"ok": False, "workflow": "browser_act", "canary": canary, "result": result, "status": zero_ai_control_workflows_status(cwd)}

    inspect = inspect_page(cwd, url)
    simulated = browser_dom_act(cwd, url, normalized_action, selector, value)
    canary["inspect"] = inspect
    canary["ok"] = bool(inspect.get("ok", False)) and bool(simulated.get("ok", False))
    result = {
        "ok": bool(canary["ok"]),
        "url": url,
        "action": normalized_action,
        "selector": selector,
        "value": value,
        "dom_action": simulated,
        "summary": "browser workflow completed a canary-backed DOM action on an allowlisted target",
    }
    _record_lane_run(
        cwd,
        "browser",
        ok=bool(result["ok"]),
        summary=str(result["summary"]),
        canary=canary,
        result=result,
        request={"url": url, "workflow": "act", "action": normalized_action, "selector": selector, "value": value},
    )
    return {"ok": bool(result["ok"]), "workflow": "browser_act", "canary": canary, "result": result, "status": zero_ai_control_workflows_status(cwd)}


def zero_ai_control_workflow_install(cwd: str, app_name: str, user_id: str = "", email: str = "", os_name: str = "") -> dict[str, Any]:
    from zero_os.app_store_production_ops import (
        account_create,
        install_app,
        license_grant,
        security_enforce,
        uninstall_app,
    )
    from zero_os.app_store_universal import list_packages, resolve_package

    state, lane = _lane_state(cwd, "store_install")
    packages = list_packages(cwd)
    available_apps = {str(app.get("name", "")).lower(): app for app in packages.get("apps", []) if str(app.get("name", "")).strip()}
    target_name = app_name.strip()
    target_key = target_name.lower()
    resolve = resolve_package(cwd, target_name, os_name)
    security = security_enforce(cwd, target_name) if target_key in available_apps else {"ok": False, "reason": "app not published"}
    canary = {
        "ok": bool(lane.get("enabled", False)) and target_key in available_apps and bool(resolve.get("ok", False)) and bool(security.get("ok", False)),
        "checks": {
            "lane_enabled": bool(lane.get("enabled", False)),
            "app_available": target_key in available_apps,
            "package_resolves": bool(resolve.get("ok", False)),
            "security_enforced": bool(security.get("ok", False)),
        },
        "resolve": resolve,
        "security": security,
    }
    if not canary["ok"]:
        reason = str(resolve.get("reason") or security.get("reason") or "store install workflow canary failed")
        result = {"ok": False, "reason": reason, "app": target_name}
        _record_lane_run(
            cwd,
            "store_install",
            ok=False,
            summary=reason,
            canary=canary,
            result=result,
            request={"app": target_name, "user_id": user_id, "email": email, "os": os_name},
        )
        return {"ok": False, "workflow": "store_install", "canary": canary, "result": result, "status": zero_ai_control_workflows_status(cwd)}

    canary_email = f"zero-ai-canary-{uuid.uuid4().hex[:8]}@{str(lane.get('canary_email_domain', 'zero-ai.local')).strip()}"
    canary_account = account_create(cwd, canary_email, tier=str(lane.get("default_tier", "free")))
    canary_license = license_grant(cwd, canary_account["user_id"], target_name)
    canary_install = install_app(cwd, canary_account["user_id"], target_name, os_name)
    canary_cleanup = uninstall_app(cwd, str((canary_install.get("install") or {}).get("install_id", ""))) if canary_install.get("ok", False) else {"ok": False, "reason": "canary install did not succeed"}
    canary["canary_account"] = canary_account
    canary["canary_license"] = canary_license
    canary["canary_install"] = canary_install
    canary["canary_cleanup"] = canary_cleanup
    canary["ok"] = bool(canary["ok"]) and bool(canary_account.get("ok", False)) and bool(canary_license.get("ok", False)) and bool(canary_install.get("ok", False)) and bool(canary_cleanup.get("ok", False))
    if not canary["ok"]:
        result = {"ok": False, "reason": "canary install sequence failed", "app": target_name}
        _record_lane_run(
            cwd,
            "store_install",
            ok=False,
            summary=str(result["reason"]),
            canary=canary,
            result=result,
            request={"app": target_name, "user_id": user_id, "email": email, "os": os_name},
        )
        return {"ok": False, "workflow": "store_install", "canary": canary, "result": result, "status": zero_ai_control_workflows_status(cwd)}

    actual_account = {"ok": True, "user_id": user_id}
    target_user = user_id.strip()
    if not target_user:
        target_email = email.strip() or f"zero-ai-user-{uuid.uuid4().hex[:8]}@{str(lane.get('canary_email_domain', 'zero-ai.local')).strip()}"
        actual_account = account_create(cwd, target_email, tier=str(lane.get("default_tier", "free")))
        target_user = str(actual_account.get("user_id", ""))
    actual_license = license_grant(cwd, target_user, target_name) if target_user else {"ok": False, "reason": "missing target user"}
    actual_install = install_app(cwd, target_user, target_name, os_name) if target_user else {"ok": False, "reason": "missing target user"}
    result = {
        "ok": bool(actual_account.get("ok", False)) and bool(actual_license.get("ok", False)) and bool(actual_install.get("ok", False)),
        "app": target_name,
        "target_user": target_user,
        "created_account": actual_account if not user_id.strip() else {},
        "license": actual_license,
        "install": actual_install,
        "summary": "store-install workflow completed a canary install, cleanup, and promoted install",
    }
    _record_lane_run(
        cwd,
        "store_install",
        ok=bool(result["ok"]),
        summary=str(result["summary"]),
        canary=canary,
        result=result,
        request={"app": target_name, "user_id": user_id, "email": email, "os": os_name},
    )
    return {"ok": bool(result["ok"]), "workflow": "store_install", "canary": canary, "result": result, "status": zero_ai_control_workflows_status(cwd)}


def zero_ai_control_workflow_recover(cwd: str, snapshot_id: str = "latest") -> dict[str, Any]:
    from zero_os.recovery import zero_ai_backup_create, zero_ai_backup_status, zero_ai_recover

    state, lane = _lane_state(cwd, "recovery")
    backup_status = zero_ai_backup_status(cwd)
    created = {}
    chosen = snapshot_id.strip() or str(lane.get("default_snapshot", "latest"))
    if int(backup_status.get("snapshot_count", 0) or 0) == 0 and chosen == "latest":
        created = zero_ai_backup_create(cwd)
        backup_status = zero_ai_backup_status(cwd)
    canary = {
        "ok": bool(lane.get("enabled", False)),
        "checks": {
            "lane_enabled": bool(lane.get("enabled", False)),
            "snapshot_available": False,
        },
        "backup_status": backup_status,
        "created_snapshot": created,
    }
    if chosen == "latest":
        chosen = str(backup_status.get("latest_snapshot", ""))
    canary["checks"]["snapshot_available"] = bool(chosen)
    canary["ok"] = bool(canary["ok"]) and bool(chosen)
    if not canary["ok"]:
        result = {"ok": False, "reason": "recovery workflow canary could not find a usable snapshot", "snapshot_id": snapshot_id}
        _record_lane_run(
            cwd,
            "recovery",
            ok=False,
            summary=str(result["reason"]),
            canary=canary,
            result=result,
            request={"snapshot_id": snapshot_id},
        )
        return {"ok": False, "workflow": "recovery", "canary": canary, "result": result, "status": zero_ai_control_workflows_status(cwd)}

    recovery = zero_ai_recover(cwd, snapshot_id=chosen)
    result = {
        "ok": bool(recovery.get("ok", False)),
        "snapshot_used": chosen,
        "recovery": recovery,
        "summary": "recovery workflow restored Zero AI from a canary-validated snapshot",
    }
    _record_lane_run(
        cwd,
        "recovery",
        ok=bool(result["ok"]),
        summary=str(result["summary"]),
        canary=canary,
        result=result,
        request={"snapshot_id": snapshot_id},
    )
    return {"ok": bool(result["ok"]), "workflow": "recovery", "canary": canary, "result": result, "status": zero_ai_control_workflows_status(cwd)}


def zero_ai_control_workflow_self_repair(cwd: str) -> dict[str, Any]:
    from zero_os.readiness import os_readiness
    from zero_os.recovery import zero_ai_backup_create, zero_ai_backup_status, zero_ai_recover
    from zero_os.self_continuity import zero_ai_self_continuity_status
    from zero_os.self_repair import self_repair_run

    state, lane = _lane_state(cwd, "self_repair")
    backup_status = zero_ai_backup_status(cwd)
    created = {}
    if int(backup_status.get("snapshot_count", 0) or 0) == 0:
        created = zero_ai_backup_create(cwd)
        backup_status = zero_ai_backup_status(cwd)
    chosen_snapshot = str(created.get("id") or backup_status.get("latest_snapshot") or "")
    continuity = zero_ai_self_continuity_status(cwd)
    continuity_block = dict(continuity.get("continuity") or {})
    contradiction_block = dict(continuity.get("contradiction_detection") or {})
    readiness_before = int((os_readiness(cwd) or {}).get("score", 0) or 0)
    canary = {
        "ok": bool(lane.get("enabled", False)) and bool(chosen_snapshot) and bool(continuity_block.get("same_system", False)) and not bool(contradiction_block.get("has_contradiction", False)),
        "checks": {
            "lane_enabled": bool(lane.get("enabled", False)),
            "snapshot_available": bool(chosen_snapshot),
            "same_system": bool(continuity_block.get("same_system", False)),
            "no_contradiction": not bool(contradiction_block.get("has_contradiction", False)),
        },
        "snapshot_id": chosen_snapshot,
        "created_snapshot": created,
        "readiness_before": readiness_before,
    }
    if not canary["ok"]:
        result = {"ok": False, "reason": "self-repair workflow canary rejected the requested repair", "snapshot_id": chosen_snapshot}
        _record_lane_run(cwd, "self_repair", ok=False, summary=str(result["reason"]), canary=canary, result=result, request={"workflow": "self_repair"})
        return {"ok": False, "workflow": "self_repair", "canary": canary, "result": result, "status": zero_ai_control_workflows_status(cwd)}

    repair = self_repair_run(cwd)
    readiness_after = int(repair.get("readiness_after", 0) or 0)
    minimum_floor = max(int(lane.get("minimum_readiness_floor", 60) or 60), readiness_before)
    promoted = bool(repair.get("ok", False)) and bool(repair.get("triad_ok", False)) and readiness_after >= minimum_floor
    rollback = {}
    if not promoted and chosen_snapshot:
        rollback = zero_ai_recover(cwd, snapshot_id=chosen_snapshot)
    result = {
        "ok": bool(promoted or rollback.get("ok", False)),
        "promoted": bool(promoted),
        "rolled_back": bool(not promoted and rollback.get("ok", False)),
        "snapshot_id": chosen_snapshot,
        "repair": repair,
        "rollback": rollback,
        "summary": (
            "self-repair workflow promoted a canary-verified repair"
            if promoted
            else "self-repair workflow rolled back to the last safe snapshot after verification failed"
        ),
    }
    _record_lane_run(
        cwd,
        "self_repair",
        ok=bool(result["ok"]),
        summary=str(result["summary"]),
        canary=canary,
        result=result,
        request={"workflow": "self_repair"},
    )
    return {"ok": bool(result["ok"]), "workflow": "self_repair", "canary": canary, "result": result, "status": zero_ai_control_workflows_status(cwd)}
