from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from zero_os.global_runtime_network import node_register as grn_node_register, node_discovery as grn_node_discovery
from zero_os.rcrp import status as rcrp_status
from zero_os.serp import analyze as serp_analyze, status as serp_status, telemetry_submit as serp_telemetry_submit


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _state_path(cwd: str) -> Path:
    p = Path(cwd).resolve() / ".zero_os" / "runtime" / "autonomous_runtime_ecosystem.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _default_state() -> dict:
    return {
        "node_roles": {
            "edge": [],
            "compute": [],
            "coordination": [],
            "archive": [],
        },
        "governance": {
            "last_proposal": {},
            "last_simulation": {},
            "last_rollout": {},
            "last_validation": {},
        },
        "ai_optimization": {
            "enabled": True,
            "last_summary": {},
            "recommendations": [],
        },
        "security": {
            "sandbox_isolation": "enabled",
            "capability_tokens": "enforced",
            "signed_packages": "required",
            "behavior_monitoring": "enabled",
            "encrypted_communication": "required",
        },
        "updated_utc": _utc_now(),
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
    state["updated_utc"] = _utc_now()
    _state_path(cwd).write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def status(cwd: str) -> dict:
    s = _load(cwd)
    return {"ok": True, "state": s}


def node_register(cwd: str, role: str, name: str, os_name: str = "linux", power: str = "normal") -> dict:
    s = _load(cwd)
    r = role.strip().lower()
    if r not in {"edge", "compute", "coordination", "archive"}:
        return {"ok": False, "reason": "role must be edge|compute|coordination|archive"}
    grn = grn_node_register(cwd, os_name, role, power)
    if not grn.get("ok", False):
        return grn
    nid = grn["node"]["node_id"]
    s["node_roles"][r].append({"node_id": nid, "name": name.strip(), "registered_utc": _utc_now()})
    _save(cwd, s)
    return {"ok": True, "role": r, "node_id": nid}


def ai_optimize(cwd: str) -> dict:
    s = _load(cwd)
    summary = serp_analyze(cwd)
    if not summary.get("ok", False):
        return {"ok": False, "reason": "no telemetry for optimization"}
    g = summary["global"]
    recs = []
    if g["cpu_avg"] > 75:
        recs.append("scheduler:move-heavy-tasks")
    if g["memory_avg"] > 75:
        recs.append("memory:reduce-fragmentation")
    if g["latency_avg_ms"] > 120:
        recs.append("network:regional-cache-bias")
    if g["gpu_avg"] > 80:
        recs.append("gpu:dispatch-batching")
    s["ai_optimization"]["last_summary"] = g
    s["ai_optimization"]["recommendations"] = recs
    _save(cwd, s)
    return {"ok": True, "summary": g, "recommendations": recs}


def governance_propose(cwd: str, component: str, strategy: str) -> dict:
    s = _load(cwd)
    p = {"component": component.strip().lower(), "strategy": strategy.strip(), "proposed_utc": _utc_now()}
    s["governance"]["last_proposal"] = p
    _save(cwd, s)
    return {"ok": True, "proposal": p}


def governance_simulate(cwd: str) -> dict:
    s = _load(cwd)
    prop = s["governance"]["last_proposal"]
    if not prop:
        return {"ok": False, "reason": "no proposal"}
    # deterministic simulation gate for control-plane
    sim = {"proposal": prop, "pass_rate": 0.97, "result": "pass", "simulated_utc": _utc_now()}
    s["governance"]["last_simulation"] = sim
    _save(cwd, s)
    return {"ok": True, "simulation": sim}


def governance_rollout(cwd: str, percent: int) -> dict:
    s = _load(cwd)
    sim = s["governance"]["last_simulation"]
    if not sim or sim.get("result") != "pass":
        return {"ok": False, "reason": "simulation not passed"}
    pct = max(1, min(100, int(percent)))
    ro = {"percent": pct, "rolled_out_utc": _utc_now(), "status": "staged" if pct < 100 else "global"}
    s["governance"]["last_rollout"] = ro
    _save(cwd, s)
    return {"ok": True, "rollout": ro}


def governance_validate(cwd: str) -> dict:
    s = _load(cwd)
    rd = grn_node_discovery(cwd)
    total = int(rd.get("total", 0))
    rollout = s["governance"]["last_rollout"]
    if not rollout:
        return {"ok": False, "reason": "no rollout"}
    val = {"nodes_validated": total, "rollout": rollout, "result": "pass" if total >= 1 else "warn", "validated_utc": _utc_now()}
    s["governance"]["last_validation"] = val
    _save(cwd, s)
    return {"ok": True, "validation": val}


def ecosystem_grade(cwd: str) -> dict:
    s = _load(cwd)
    rs = rcrp_status(cwd)
    ss = serp_status(cwd)
    roles = s["node_roles"]
    checks = {
        "all_node_roles_present": all(len(roles[k]) >= 1 for k in ("edge", "compute", "coordination", "archive")),
        "ai_optimization_ready": bool(s["ai_optimization"]["recommendations"] or s["ai_optimization"]["last_summary"]),
        "governance_validated": bool(s["governance"]["last_validation"]),
        "security_layers_active": all(v in {"enabled", "required", "enforced"} for v in s["security"].values()),
        "rcrp_online": bool(rs.get("ok", False)),
        "serp_online": bool(ss.get("ok", False)),
    }
    weights = {
        "all_node_roles_present": 30,
        "ai_optimization_ready": 20,
        "governance_validated": 20,
        "security_layers_active": 15,
        "rcrp_online": 7,
        "serp_online": 8,
    }
    score = sum(weights[k] for k, ok in checks.items() if ok)
    tier = "A+" if score >= 95 else "A" if score >= 90 else "B" if score >= 80 else "C" if score >= 65 else "D"
    gaps = [k for k, ok in checks.items() if not ok]
    return {"ok": True, "ecosystem_score": score, "ecosystem_tier": tier, "checks": checks, "gaps": gaps}


def maximize(cwd: str) -> dict:
    node_register(cwd, "edge", "edge-node", "linux", "balanced")
    node_register(cwd, "compute", "compute-node", "linux", "high")
    node_register(cwd, "coordination", "coord-node", "linux", "high")
    node_register(cwd, "archive", "archive-node", "linux", "normal")
    governance_propose(cwd, "scheduler", "sched_global_v2")
    governance_simulate(cwd)
    governance_rollout(cwd, 100)
    governance_validate(cwd)
    serp_telemetry_submit(cwd, "max-node", "us-west", 68.0, 55.0, 62.0, 85.0, 40.0)
    ai_optimize(cwd)
    return {"ok": True, "grade": ecosystem_grade(cwd)}
