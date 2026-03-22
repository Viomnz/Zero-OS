from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from zero_os.approval_workflow import latest_approved, mark_executed, request_approval


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _assistant_dir(cwd: str) -> Path:
    path = Path(cwd).resolve() / ".zero_os" / "assistant"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _path(cwd: str) -> Path:
    return _assistant_dir(cwd) / "communications.json"


def _load(path: Path, default: dict) -> dict:
    if not path.exists():
        return dict(default)
    try:
        raw = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return dict(default)
    if not isinstance(raw, dict):
        return dict(default)
    merged = dict(default)
    merged.update(raw)
    return merged


def _save(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _default_state() -> dict:
    return {
        "schema_version": 1,
        "enabled": True,
        "last_refreshed_utc": "",
        "drafts": [],
        "outbox": [],
        "audit": [],
    }


def _state(cwd: str) -> dict:
    return _load(_path(cwd), _default_state())


def _summarize(state: dict, cwd: str) -> dict:
    state["ok"] = True
    state["path"] = str(_path(cwd))
    state["summary"] = {
        "enabled": bool(state.get("enabled", True)),
        "draft_count": len(list(state.get("drafts", []))),
        "outbox_count": len(list(state.get("outbox", []))),
        "audit_count": len(list(state.get("audit", []))),
    }
    return state


def communications_status(cwd: str) -> dict:
    state = _summarize(_state(cwd), cwd)
    _save(_path(cwd), state)
    return state


def communications_refresh(cwd: str) -> dict:
    state = _state(cwd)
    state["last_refreshed_utc"] = _utc_now()
    state.setdefault("audit", []).append({"time_utc": _utc_now(), "action": "refresh"})
    state = _summarize(state, cwd)
    _save(_path(cwd), state)
    return state


def communications_draft_add(cwd: str, recipient: str, message: str) -> dict:
    state = _state(cwd)
    draft = {
        "id": f"draft_{len(list(state.get('drafts', []))) + 1}",
        "time_utc": _utc_now(),
        "recipient": recipient.strip(),
        "message": message.strip(),
        "status": "draft",
    }
    state.setdefault("drafts", []).append(draft)
    state.setdefault("audit", []).append(
        {
            "time_utc": draft["time_utc"],
            "action": "draft_add",
            "recipient": draft["recipient"],
        }
    )
    state = _summarize(state, cwd)
    _save(_path(cwd), state)
    return {"ok": True, "draft": draft, "summary": state["summary"], "path": state["path"]}


def communications_send_request(cwd: str, draft_id: str, *, run_id: str = "") -> dict:
    state = _state(cwd)
    drafts = list(state.get("drafts", []))
    for draft in drafts:
        if str(draft.get("id", "")) != str(draft_id).strip():
            continue
        approval = request_approval(
            cwd,
            "communications_send",
            "Outbound communication requires explicit approval before send.",
            payload={
                "draft_id": draft["id"],
                "recipient": draft.get("recipient", ""),
                "run_id": run_id,
                "target": {
                    "draft_id": draft["id"],
                    "recipient": draft.get("recipient", ""),
                    "run_id": run_id,
                },
            },
        )
        state.setdefault("audit", []).append(
            {
                "time_utc": _utc_now(),
                "action": "send_requested",
                "draft_id": draft["id"],
                "approval_id": approval["approval"]["id"],
            }
        )
        state = _summarize(state, cwd)
        _save(_path(cwd), state)
        return {
            "ok": True,
            "draft": draft,
            "approval": approval["approval"],
            "summary": state["summary"],
            "path": state["path"],
        }
    return {"ok": False, "reason": "draft not found"}


def communications_send_execute(cwd: str, draft_id: str, *, run_id: str = "") -> dict:
    state = _state(cwd)
    drafts = list(state.get("drafts", []))
    for index, draft in enumerate(drafts):
        if str(draft.get("id", "")) != str(draft_id).strip():
            continue
        approved = latest_approved(
            cwd,
            "communications_send",
            run_id=run_id,
            target={"draft_id": draft["id"], "recipient": draft.get("recipient", ""), "run_id": run_id},
        )
        if not approved.get("ok", False):
            return {"ok": False, "reason": "approval_required", "draft": draft}
        approval = dict(approved.get("approval") or {})
        sent = dict(draft)
        sent["status"] = "sent"
        sent["sent_utc"] = _utc_now()
        state.setdefault("outbox", []).append(sent)
        drafts.pop(index)
        state["drafts"] = drafts
        state.setdefault("audit", []).append(
            {
                "time_utc": sent["sent_utc"],
                "action": "send_executed",
                "draft_id": sent["id"],
                "approval_id": approval.get("id", ""),
            }
        )
        mark_executed(cwd, str(approval.get("id", "")), outcome="sent")
        state = _summarize(state, cwd)
        _save(_path(cwd), state)
        return {"ok": True, "sent": sent, "summary": state["summary"], "path": state["path"]}
    return {"ok": False, "reason": "draft not found"}


def communications_tick(cwd: str) -> dict:
    state = _state(cwd)
    executed: list[dict] = []
    for draft in list(state.get("drafts", [])):
        result = communications_send_execute(cwd, str(draft.get("id", "")))
        if bool(result.get("ok", False)):
            executed.append(dict(result.get("sent") or {}))
    refreshed = communications_status(cwd)
    return {
        "ok": True,
        "executed_count": len(executed),
        "executed": executed,
        "summary": refreshed["summary"],
        "path": refreshed["path"],
    }
