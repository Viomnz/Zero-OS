from __future__ import annotations

import json
import webbrowser
from pathlib import Path


def _session_path(cwd: str) -> Path:
    path = Path(cwd).resolve() / ".zero_os" / "connectors" / "browser_session.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(json.dumps({"tabs": [], "last_opened": ""}, indent=2) + "\n", encoding="utf-8")
    return path


def browser_session_status(cwd: str) -> dict:
    return json.loads(_session_path(cwd).read_text(encoding="utf-8", errors="replace"))


def browser_session_open(cwd: str, url: str) -> dict:
    opened = bool(webbrowser.open(url, new=2))
    data = browser_session_status(cwd)
    data.setdefault("tabs", []).append({"url": url, "opened": opened})
    data["tabs"] = data["tabs"][-20:]
    data["last_opened"] = url
    _session_path(cwd).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return {"ok": True, "url": url, "opened": opened, "session": data}


def browser_session_action(cwd: str, action: str, selector: str = "", value: str = "") -> dict:
    data = browser_session_status(cwd)
    event = {
        "action": action,
        "selector": selector,
        "value": value,
        "target": data.get("last_opened", ""),
        "simulated": True,
    }
    data.setdefault("actions", []).append(event)
    data["actions"] = data["actions"][-50:]
    _session_path(cwd).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return {"ok": True, "action": event, "session": data}
