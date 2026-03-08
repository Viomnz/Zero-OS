from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _state_path(cwd: str) -> Path:
    p = Path(cwd).resolve() / ".zero_os" / "runtime" / "rcrp_state.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _default_state() -> dict:
    return {
        "graphs": {},
        "device_profile": {
            "cpu": "x86_64",
            "gpu": "integrated",
            "ram_gb": 8,
            "network": "normal",
            "sensors": [],
            "energy_mode": "balanced",
        },
        "mesh": {"local_node": "", "regional_cluster": "us-west", "global_mesh": "online", "nodes": {}},
        "tokens": {"camera_access_token": False, "network_access_token": True, "filesystem_token": True},
        "plans": {},
        "migrations": [],
        "learning": {"observations": [], "adjustments": []},
    }


def _load(cwd: str) -> dict:
    p = _state_path(cwd)
    if not p.exists():
        d = _default_state()
        _save(cwd, d)
        return d
    try:
        return json.loads(p.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        d = _default_state()
        _save(cwd, d)
        return d


def _save(cwd: str, state: dict) -> None:
    _state_path(cwd).write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def status(cwd: str) -> dict:
    s = _load(cwd)
    return {"ok": True, "graphs": len(s["graphs"]), "plans": len(s["plans"]), "mesh": s["mesh"], "device_profile": s["device_profile"]}


def device_profile_set(cwd: str, cpu: str = "", gpu: str = "", ram_gb: int | None = None, network: str = "", energy: str = "") -> dict:
    s = _load(cwd)
    d = s["device_profile"]
    if cpu:
        d["cpu"] = cpu
    if gpu:
        d["gpu"] = gpu
    if ram_gb is not None:
        d["ram_gb"] = max(1, int(ram_gb))
    if network:
        d["network"] = network
    if energy:
        d["energy_mode"] = energy
    _save(cwd, s)
    return {"ok": True, "device_profile": d}


def graph_register(cwd: str, app: str, graph_json: str) -> dict:
    s = _load(cwd)
    try:
        g = json.loads(graph_json)
    except Exception:
        return {"ok": False, "reason": "invalid graph json"}
    if "nodes" not in g or "edges" not in g:
        return {"ok": False, "reason": "graph requires nodes and edges"}
    s["graphs"][app] = {"graph": g, "registered_utc": _utc_now()}
    _save(cwd, s)
    return {"ok": True, "app": app, "node_count": len(g.get("nodes", []))}


def token_set(cwd: str, token: str, enabled: bool) -> dict:
    s = _load(cwd)
    s["tokens"][token.strip()] = bool(enabled)
    _save(cwd, s)
    return {"ok": True, "tokens": s["tokens"]}


def _strategy(node: dict, device: dict) -> str:
    kind = str(node.get("type", "")).lower()
    if kind == "graphics" and ("discrete" in device["gpu"] or "vulkan" in device["gpu"]):
        return "gpu-offload"
    if device["energy_mode"] == "low-power":
        return "bytecode"
    if "x86" in device["cpu"] and device["ram_gb"] >= 16:
        return "native-jit"
    return "bytecode"


def plan_build(cwd: str, app: str) -> dict:
    s = _load(cwd)
    entry = s["graphs"].get(app)
    if not entry:
        return {"ok": False, "reason": "graph not found"}
    g = entry["graph"]
    plan = []
    for n in g.get("nodes", []):
        node_id = str(n.get("id", "node"))
        kind = str(n.get("type", "compute")).lower()
        token = str(n.get("token", "")).strip()
        if token and not bool(s["tokens"].get(token, False)):
            return {"ok": False, "reason": f"missing token for node {node_id}", "token": token}
        plan.append({"id": node_id, "type": kind, "strategy": _strategy(n, s["device_profile"])})
    pid = str(uuid.uuid4())[:12]
    rec = {"plan_id": pid, "app": app, "steps": plan, "created_utc": _utc_now()}
    s["plans"][pid] = rec
    _save(cwd, s)
    return {"ok": True, "plan": rec}


def mesh_node_register(cwd: str, node_name: str, power: str) -> dict:
    s = _load(cwd)
    nid = str(uuid.uuid4())[:10]
    s["mesh"]["nodes"][nid] = {"name": node_name, "power": power, "registered_utc": _utc_now()}
    if not s["mesh"]["local_node"]:
        s["mesh"]["local_node"] = nid
    _save(cwd, s)
    return {"ok": True, "node_id": nid, "mesh": s["mesh"]}


def migrate(cwd: str, app: str, plan_id: str, target_node: str) -> dict:
    s = _load(cwd)
    if plan_id not in s["plans"]:
        return {"ok": False, "reason": "plan not found"}
    if target_node not in s["mesh"]["nodes"]:
        return {"ok": False, "reason": "target node not found"}
    rec = {
        "time_utc": _utc_now(),
        "app": app,
        "plan_id": plan_id,
        "target_node": target_node,
        "state_snapshot": {"memory": "snapshot-v1", "graph_cursor": 0},
    }
    s["migrations"].append(rec)
    s["migrations"] = s["migrations"][-200:]
    _save(cwd, s)
    return {"ok": True, "migration": rec}


def learning_observe(cwd: str, observation: str) -> dict:
    s = _load(cwd)
    obs = observation.strip().lower()
    s["learning"]["observations"].append({"time_utc": _utc_now(), "observation": obs})
    adj = ""
    if "cpu overload" in obs:
        adj = "move tasks to gpu"
    elif "network delay" in obs:
        adj = "cache assets locally"
    elif "memory pressure" in obs:
        adj = "compress runtime state"
    if adj:
        s["learning"]["adjustments"].append({"time_utc": _utc_now(), "adjustment": adj})
    _save(cwd, s)
    return {"ok": True, "adjustment": adj or "none"}
