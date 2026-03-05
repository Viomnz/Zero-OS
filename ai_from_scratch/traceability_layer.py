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


def log_decision_trace(cwd: str, trace: dict) -> dict:
    rt = _runtime(cwd)
    path = rt / "decision_trace.json"
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            data = {"history": []}
    else:
        data = {"history": []}

    entry = {"time_utc": _utc_now(), **trace}
    history = list(data.get("history", []))
    history.append(entry)
    data["history"] = history[-400:]
    data["last"] = entry
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return {
        "ok": True,
        "entry_index": len(data["history"]) - 1,
        "history_size": len(data["history"]),
        "path": str(path),
    }

