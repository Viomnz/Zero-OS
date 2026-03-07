from __future__ import annotations

import json
import time
from pathlib import Path


def _runtime(cwd: str) -> Path:
    p = Path(cwd).resolve() / ".zero_os" / "runtime"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _limits_path(cwd: str) -> Path:
    return _runtime(cwd) / "rate_limits.json"


def _load(cwd: str) -> dict:
    p = _limits_path(cwd)
    if not p.exists():
        return {}
    try:
        raw = json.loads(p.read_text(encoding="utf-8", errors="replace"))
        return raw if isinstance(raw, dict) else {}
    except Exception:
        return {}


def _save(cwd: str, payload: dict) -> None:
    _limits_path(cwd).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def check_and_record(cwd: str, channel: str, limit: int, window_seconds: int) -> tuple[bool, dict]:
    now = time.time()
    cap = max(1, int(limit))
    window = max(1, int(window_seconds))
    data = _load(cwd)
    key = channel.strip().lower()
    rec = data.get(key, {"events": []})
    events = [float(ts) for ts in rec.get("events", []) if isinstance(ts, (int, float))]
    events = [ts for ts in events if now - ts <= window]
    if len(events) >= cap:
        retry_after = max(1, int(window - (now - min(events))))
        state = {
            "channel": key,
            "limit": cap,
            "window_seconds": window,
            "used": len(events),
            "retry_after_seconds": retry_after,
        }
        return (False, state)

    events.append(now)
    data[key] = {"events": events}
    _save(cwd, data)
    state = {
        "channel": key,
        "limit": cap,
        "window_seconds": window,
        "used": len(events),
        "retry_after_seconds": 0,
    }
    return (True, state)
