from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


def _runtime(cwd: str) -> Path:
    p = Path(cwd).resolve() / ".zero_os" / "runtime"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_trace(path: Path) -> dict:
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            data = {"history": []}
    else:
        data = {"history": []}
    if not isinstance(data.get("history", []), list):
        data["history"] = []
    return data


def _save_trace(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def log_decision_trace(cwd: str, trace: dict) -> dict:
    rt = _runtime(cwd)
    path = rt / "decision_trace.json"
    data = _load_trace(path)

    entry = {
        "time_utc": _utc_now(),
        "event_type": "decision",
        "schema_version": 2,
        "input": trace.get("input", {}),
        "context": trace.get("context", {}),
        "reasoning_path": trace.get("meta_reasoning", {}),
        "evaluation_results": {
            "signals": trace.get("signals", {}),
            "consensus": trace.get("consensus", {}),
            "safe_state": trace.get("safe_state", {}),
        },
        "executed_action": trace.get("final_action", {}),
        "observed_outcome": trace.get("observed_outcome", {}),
        "result_metrics": trace.get("result_metrics", {}),
        "raw": trace,
    }
    history = list(data.get("history", []))
    history.append(entry)
    data["history"] = history[-400:]
    data["last"] = entry
    _save_trace(path, data)
    return {
        "ok": True,
        "entry_index": len(data["history"]) - 1,
        "history_size": len(data["history"]),
        "path": str(path),
    }


def log_trace_event(cwd: str, event_type: str, payload: dict) -> dict:
    rt = _runtime(cwd)
    path = rt / "decision_trace.json"
    data = _load_trace(path)
    entry = {
        "time_utc": _utc_now(),
        "event_type": str(event_type or "event"),
        "schema_version": 2,
        "payload": payload or {},
    }
    history = list(data.get("history", []))
    history.append(entry)
    data["history"] = history[-400:]
    data["last"] = entry
    _save_trace(path, data)
    return {"ok": True, "event_type": entry["event_type"], "history_size": len(data["history"]), "path": str(path)}


def audit_trace(cwd: str, limit: int = 50, event_type: str | None = None) -> dict:
    rt = _runtime(cwd)
    path = rt / "decision_trace.json"
    data = _load_trace(path)
    history = list(data.get("history", []))
    if event_type:
        history = [h for h in history if str(h.get("event_type", "")).lower() == str(event_type).lower()]
    events = history[-max(1, int(limit)) :]
    return {
        "ok": True,
        "path": str(path),
        "total": len(history),
        "returned": len(events),
        "events": events,
    }
