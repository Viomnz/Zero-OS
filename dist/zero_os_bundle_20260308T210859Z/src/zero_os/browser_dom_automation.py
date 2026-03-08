from __future__ import annotations

import json
from pathlib import Path


def _path(cwd: str) -> Path:
    path = Path(cwd).resolve() / ".zero_os" / "connectors" / "browser_dom.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(json.dumps({"pages": {}, "last_selector": ""}, indent=2) + "\n", encoding="utf-8")
    return path


def status(cwd: str) -> dict:
    return json.loads(_path(cwd).read_text(encoding="utf-8", errors="replace"))


def inspect_page(cwd: str, url: str) -> dict:
    data = status(cwd)
    page = {
        "url": url,
        "selectors": ["body", "a", "input", "button", "#main"],
        "interactive": True,
    }
    data.setdefault("pages", {})[url] = page
    _path(cwd).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return {"ok": True, "page": page}


def act(cwd: str, url: str, action: str, selector: str, value: str = "") -> dict:
    data = status(cwd)
    data["last_selector"] = selector
    data.setdefault("actions", []).append({"url": url, "action": action, "selector": selector, "value": value, "simulated": True})
    data["actions"] = data["actions"][-50:]
    _path(cwd).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return {"ok": True, "action": {"url": url, "action": action, "selector": selector, "value": value, "simulated": True}}
