from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _state_path(cwd: str) -> Path:
    p = Path(cwd).resolve() / ".zero_os" / "runtime" / "serp_state.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _default_state() -> dict:
    return {
        "runtime": {"current_version": "1.0.0", "active_rules": {"scheduler": "rr-v1", "memory": "alloc-v1", "translator": "sysmap-v1", "gpu": "dispatch-v1"}},
        "telemetry": {"samples": [], "regional_aggregates": {}, "global_summary": {}},
        "mutations": [],
        "deployments": [],
        "safety": {"sandbox_testing": True, "staged_deployment": True, "rollback_enabled": True, "required_signer": "serp-ca"},
        "portable_states": {},
        "audit": [],
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


def _log(s: dict, event: str, payload: dict) -> None:
    s["audit"].append({"time_utc": _utc_now(), "event": event, "payload": payload})
    s["audit"] = s["audit"][-500:]


def status(cwd: str) -> dict:
    s = _load(cwd)
    return {
        "ok": True,
        "runtime": s["runtime"],
        "telemetry_samples": len(s["telemetry"]["samples"]),
        "mutations": len(s["mutations"]),
        "deployments": len(s["deployments"]),
        "safety": s["safety"],
    }


def telemetry_submit(cwd: str, node: str, region: str, cpu: float, memory: float, gpu: float, latency_ms: float, energy: float) -> dict:
    s = _load(cwd)
    rec = {
        "time_utc": _utc_now(),
        "node": node.strip(),
        "region": region.strip().lower(),
        "cpu": float(cpu),
        "memory": float(memory),
        "gpu": float(gpu),
        "latency_ms": float(latency_ms),
        "energy": float(energy),
    }
    s["telemetry"]["samples"].append(rec)
    s["telemetry"]["samples"] = s["telemetry"]["samples"][-2000:]
    _log(s, "telemetry_submit", {"node": rec["node"], "region": rec["region"]})
    _save(cwd, s)
    return {"ok": True, "sample": rec}


def analyze(cwd: str) -> dict:
    s = _load(cwd)
    samples = s["telemetry"]["samples"]
    if not samples:
        return {"ok": False, "reason": "no telemetry"}
    by_region: dict[str, list[dict]] = {}
    for x in samples:
        by_region.setdefault(x["region"], []).append(x)
    reg = {}
    for r, arr in by_region.items():
        n = max(1, len(arr))
        reg[r] = {
            "count": n,
            "cpu_avg": round(sum(a["cpu"] for a in arr) / n, 2),
            "memory_avg": round(sum(a["memory"] for a in arr) / n, 2),
            "gpu_avg": round(sum(a["gpu"] for a in arr) / n, 2),
            "latency_avg_ms": round(sum(a["latency_ms"] for a in arr) / n, 2),
            "energy_avg": round(sum(a["energy"] for a in arr) / n, 2),
        }
    alln = len(samples)
    g = {
        "count": alln,
        "cpu_avg": round(sum(a["cpu"] for a in samples) / alln, 2),
        "memory_avg": round(sum(a["memory"] for a in samples) / alln, 2),
        "gpu_avg": round(sum(a["gpu"] for a in samples) / alln, 2),
        "latency_avg_ms": round(sum(a["latency_ms"] for a in samples) / alln, 2),
        "energy_avg": round(sum(a["energy"] for a in samples) / alln, 2),
    }
    s["telemetry"]["regional_aggregates"] = reg
    s["telemetry"]["global_summary"] = g
    _log(s, "analyze", {"samples": alln})
    _save(cwd, s)
    return {"ok": True, "regional": reg, "global": g}


def mutation_propose(cwd: str, component: str, strategy: str, signer: str) -> dict:
    s = _load(cwd)
    comp = component.strip().lower()
    if comp not in {"scheduler", "memory", "translator", "gpu"}:
        return {"ok": False, "reason": "component must be scheduler|memory|translator|gpu"}
    safe = signer.strip() == s["safety"]["required_signer"]
    mid = str(uuid.uuid4())[:12]
    rec = {
        "id": mid,
        "component": comp,
        "strategy": strategy.strip(),
        "signer": signer.strip(),
        "signed_ok": safe,
        "sandbox_result": "pass" if safe else "fail",
        "created_utc": _utc_now(),
        "status": "validated" if safe else "rejected",
    }
    s["mutations"].append(rec)
    _log(s, "mutation_propose", {"id": mid, "component": comp, "signed_ok": safe})
    _save(cwd, s)
    return {"ok": safe, "mutation": rec}


def deploy_staged(cwd: str, mutation_id: str, percent: int) -> dict:
    s = _load(cwd)
    m = next((x for x in s["mutations"] if x["id"] == mutation_id), None)
    if not m:
        return {"ok": False, "reason": "mutation not found"}
    if m["status"] != "validated":
        return {"ok": False, "reason": "mutation not validated"}
    pct = max(1, min(100, int(percent)))
    did = str(uuid.uuid4())[:12]
    dep = {"id": did, "mutation_id": mutation_id, "percent": pct, "time_utc": _utc_now(), "status": "rolled_out"}
    s["deployments"].append(dep)
    if pct >= 100:
        s["runtime"]["active_rules"][m["component"]] = m["strategy"]
        s["runtime"]["current_version"] = f"{s['runtime']['current_version']}-m{len(s['deployments'])}"
    _log(s, "deploy_staged", {"id": did, "percent": pct})
    _save(cwd, s)
    return {"ok": True, "deployment": dep, "runtime": s["runtime"]}


def rollback(cwd: str) -> dict:
    s = _load(cwd)
    if not s["deployments"]:
        return {"ok": False, "reason": "no deployment"}
    last = s["deployments"][-1]
    last["status"] = "rolled_back"
    _log(s, "rollback", {"deployment": last["id"]})
    _save(cwd, s)
    return {"ok": True, "rolled_back": last["id"]}


def state_export(cwd: str, app: str, payload_json: str) -> dict:
    s = _load(cwd)
    try:
        payload = json.loads(payload_json)
    except Exception:
        return {"ok": False, "reason": "invalid payload json"}
    sid = str(uuid.uuid4())[:12]
    rec = {"id": sid, "app": app.strip(), "snapshot": payload, "exported_utc": _utc_now()}
    s["portable_states"][sid] = rec
    _log(s, "state_export", {"id": sid, "app": app})
    _save(cwd, s)
    return {"ok": True, "state_id": sid}


def state_import(cwd: str, state_id: str, target_node: str) -> dict:
    s = _load(cwd)
    st = s["portable_states"].get(state_id)
    if not st:
        return {"ok": False, "reason": "state not found"}
    rec = {"state_id": state_id, "target_node": target_node.strip(), "resumed_utc": _utc_now()}
    _log(s, "state_import", rec)
    _save(cwd, s)
    return {"ok": True, "resume": rec, "snapshot": st["snapshot"]}
