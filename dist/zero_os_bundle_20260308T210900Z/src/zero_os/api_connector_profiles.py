from __future__ import annotations

import json
from pathlib import Path

from zero_os.net_client import request_text


def _profiles_path(cwd: str) -> Path:
    path = Path(cwd).resolve() / ".zero_os" / "connectors" / "api_profiles.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(json.dumps({"profiles": {}}, indent=2) + "\n", encoding="utf-8")
    return path


def profile_status(cwd: str) -> dict:
    return json.loads(_profiles_path(cwd).read_text(encoding="utf-8", errors="replace"))


def profile_set(cwd: str, name: str, base_url: str, token: str = "") -> dict:
    data = profile_status(cwd)
    data.setdefault("profiles", {})[name] = {
        "base_url": base_url,
        "token": token,
        "schema": {"pagination": False, "auth": "bearer" if token else "none"},
    }
    _profiles_path(cwd).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return {"ok": True, "profile": data["profiles"][name]}


def profile_request(cwd: str, name: str, path: str) -> dict:
    data = profile_status(cwd)
    profile = data.get("profiles", {}).get(name)
    if not profile:
        return {"ok": False, "reason": "profile not found"}
    url = str(profile.get("base_url", "")).rstrip("/") + "/" + path.lstrip("/")
    headers = {}
    token = str(profile.get("token", "")).strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return request_text(url, headers=headers, timeout=8, retries=1)


def profile_workflow(cwd: str, name: str, paths: list[str]) -> dict:
    results = []
    for path in paths:
        results.append(profile_request(cwd, name, path))
    schema = profile_status(cwd).get("profiles", {}).get(name, {}).get("schema", {})
    return {"ok": all(item.get("ok", False) for item in results), "profile": name, "schema": schema, "results": results}
