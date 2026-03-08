from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from zero_os.rcrp import status as rcrp_status
from zero_os.serp import analyze as serp_analyze


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _state_path(cwd: str) -> Path:
    p = Path(cwd).resolve() / ".zero_os" / "runtime" / "hardware_runtime_fabric.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _default_state() -> dict:
    return {
        "hardware_modules": {
            "runtime_accelerator": False,
            "security_coprocessor": False,
            "memory_optimizer": False,
            "network_offload_engine": False,
        },
        "app_evolution": {"history": []},
        "persistent_memory": {"patterns": {}},
        "fabric": {"dispatches": [], "cluster_nodes": {}},
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
    return {
        "ok": True,
        "hardware_modules": s["hardware_modules"],
        "app_evolution_events": len(s["app_evolution"]["history"]),
        "persistent_patterns": len(s["persistent_memory"]["patterns"]),
        "fabric_dispatches": len(s["fabric"]["dispatches"]),
    }


def hardware_set(cwd: str, accelerator: bool | None = None, security: bool | None = None, memory: bool | None = None, network: bool | None = None) -> dict:
    s = _load(cwd)
    m = s["hardware_modules"]
    if accelerator is not None:
        m["runtime_accelerator"] = bool(accelerator)
    if security is not None:
        m["security_coprocessor"] = bool(security)
    if memory is not None:
        m["memory_optimizer"] = bool(memory)
    if network is not None:
        m["network_offload_engine"] = bool(network)
    _save(cwd, s)
    return {"ok": True, "hardware_modules": m}


def hardware_maximize(cwd: str) -> dict:
    return hardware_set(cwd, True, True, True, True)


def evolve_application(cwd: str, app: str) -> dict:
    s = _load(cwd)
    analysis = serp_analyze(cwd)
    # Non-fatal if no telemetry; still produce baseline proposal.
    recs = []
    if analysis.get("ok", False):
        g = analysis.get("global", {})
        if float(g.get("gpu_avg", 0)) > 70:
            recs.append("rendering:pipeline_gpu_batch_v2")
        if float(g.get("latency_avg_ms", 0)) > 100:
            recs.append("network:request_batching_v2")
        if float(g.get("memory_avg", 0)) > 70:
            recs.append("memory:layout_compaction_v2")
    if not recs:
        recs.append("scheduler:balanced_graph_v2")
    evt = {"time_utc": _utc_now(), "app": app.strip(), "recommendations": recs}
    s["app_evolution"]["history"].append(evt)
    s["app_evolution"]["history"] = s["app_evolution"]["history"][-500:]
    _save(cwd, s)
    return {"ok": True, "evolution": evt}


def memory_learn(cwd: str, app: str, key: str, value: str) -> dict:
    s = _load(cwd)
    bucket = s["persistent_memory"]["patterns"].setdefault(app.strip(), {})
    bucket[key.strip()] = {"value": value, "updated_utc": _utc_now()}
    _save(cwd, s)
    return {"ok": True, "app": app.strip(), "patterns": bucket}


def memory_get(cwd: str, app: str) -> dict:
    s = _load(cwd)
    return {"ok": True, "app": app.strip(), "patterns": s["persistent_memory"]["patterns"].get(app.strip(), {})}


def fabric_node_register(cwd: str, name: str, power: str) -> dict:
    s = _load(cwd)
    nid = str(uuid.uuid4())[:10]
    s["fabric"]["cluster_nodes"][nid] = {"name": name.strip(), "power": power.strip(), "registered_utc": _utc_now()}
    _save(cwd, s)
    return {"ok": True, "node_id": nid}


def fabric_dispatch(cwd: str, app: str, task: str, nodes: int = 1) -> dict:
    s = _load(cwd)
    node_ids = list(s["fabric"]["cluster_nodes"].keys())
    if not node_ids:
        return {"ok": False, "reason": "no cluster nodes registered"}
    n = max(1, int(nodes))
    selected = node_ids[: min(n, len(node_ids))]
    rec = {
        "dispatch_id": str(uuid.uuid4())[:12],
        "time_utc": _utc_now(),
        "app": app.strip(),
        "task": task.strip(),
        "nodes": selected,
    }
    s["fabric"]["dispatches"].append(rec)
    s["fabric"]["dispatches"] = s["fabric"]["dispatches"][-500:]
    _save(cwd, s)
    return {"ok": True, "dispatch": rec}


def fabric_status(cwd: str) -> dict:
    s = _load(cwd)
    return {
        "ok": True,
        "cluster_nodes": s["fabric"]["cluster_nodes"],
        "dispatch_count": len(s["fabric"]["dispatches"]),
        "latest_dispatches": s["fabric"]["dispatches"][-20:],
        "rcrp_online": bool(rcrp_status(cwd).get("ok", False)),
    }
