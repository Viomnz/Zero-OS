from __future__ import annotations

import json
from pathlib import Path


def _path(cwd: str) -> Path:
    path = Path(cwd).resolve() / ".zero_os" / "integrations" / "cloud_deploy.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(json.dumps({"targets": {}, "deployments": []}, indent=2) + "\n", encoding="utf-8")
    return path


def status(cwd: str) -> dict:
    return json.loads(_path(cwd).read_text(encoding="utf-8", errors="replace"))


def configure_target(cwd: str, name: str, provider: str) -> dict:
    data = status(cwd)
    data.setdefault("targets", {})[name] = {"provider": provider, "configured": True}
    _path(cwd).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return {"ok": True, "target": name}


def deploy(cwd: str, target: str, artifact: str) -> dict:
    data = status(cwd)
    rec = {"target": target, "artifact": artifact, "simulated": True}
    data.setdefault("deployments", []).append(rec)
    _path(cwd).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return {"ok": True, "deployment": rec}
