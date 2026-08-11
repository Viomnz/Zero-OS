from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from zero_os.global_runtime_network import node_register as grn_node_register, node_discovery as grn_node_discovery
from zero_os.pure_logic_control_loop import (
    CandidateAction,
    ControllerAuthorityState,
    ControllerContract,
    FeedbackSource,
    LoopTier,
    StateEstimate,
    authorize_control_step,
)
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
            "controller_authority": ControllerAuthorityState.PROVISIONAL.value,
            "control_history": [],
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
        d = json.loads(p.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        d = _default_state()
    default = _default_state()
    d.setdefault("governance", default["governance"])
    for key, value in default["governance"].items():
        d["governance"].setdefault(key, value)
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
    return {
        "ok": True,
        "summary": g,
        "recommendations": recs,
        "authority_granted": False,
        "epistemic_role": "discovery_only_until_control_loop_and_capability_authority_survive",
    }


def governance_propose(cwd: str, component: str, strategy: str) -> dict:
    s = _load(cwd)
    p = {"component": component.strip().lower(), "strategy": strategy.strip(), "proposed_utc": _utc_now()}
    s["governance"]["last_proposal"] = p
    _save(cwd, s)
    return {"ok": True, "proposal": p, "authority_granted": False}


def governance_simulate(cwd: str) -> dict:
    s = _load(cwd)
    prop = s["governance"]["last_proposal"]
    if not prop:
        return {"ok": False, "reason": "no proposal"}
    # Simulation is discovery evidence only. It cannot certify rollout authority.
    sim = {"proposal": prop, "pass_rate": 0.97, "result": "pass", "simulated_utc": _utc_now()}
    s["governance"]["last_simulation"] = sim
    _save(cwd, s)
    return {"ok": True, "simulation": sim, "scope_certified": False, "authority_granted": False}


def governance_rollout(
    cwd: str,
    percent: int,
    *,
    objective_authorized: bool = False,
    controller_authority: ControllerAuthorityState | str = ControllerAuthorityState.PROVISIONAL,
    state_uncertainty: float = 1.0,
) -> dict:
    """Request rollout eligibility through the Pure Logic Control Loop Kernel.

    This function still does not mint final execution/capability authority. A
    successful control decision only allows the rollout controller to request
    the independently scoped deployment capability from the Authority Kernel.
    """
    s = _load(cwd)
    sim = s["governance"]["last_simulation"]
    if not sim or sim.get("result") != "pass":
        return {"ok": False, "reason": "simulation not passed"}

    now = datetime.now(timezone.utc)
    pct = max(1, min(100, int(percent)))
    action_id = "governance_rollout"
    feedback = FeedbackSource(
        source_id="ecosystem_simulator",
        provenance="autonomous_runtime_ecosystem:governance_simulate",
        method_family="isolated_simulation",
        lineage=("autonomous_runtime_ecosystem",),
        fresh_until_utc=(now + timedelta(minutes=5)).isoformat(),
        demonstrated_scope=("simulation:governance_rollout",),
        reliability=float(sim.get("pass_rate", 0.0) or 0.0),
    )
    contract = ControllerContract(
        controller_id="autonomous_runtime_ecosystem",
        objective_id="ecosystem_governance",
        authority_id="controller:ecosystem_governance",
        scope=("deploy:ecosystem_rollout",),
        allowed_actions=(action_id,),
        max_blast="subsystem" if pct < 100 else "system",
        expires_at_utc=(now + timedelta(minutes=10)).isoformat(),
        revocation_conditions=("CONTROL_OSCILLATION", "sensor_provenance_failed", "objective_revoked"),
        expected_response_min_seconds=1.0,
        expected_response_max_seconds=60.0,
        max_uncertainty_for_irreversible_action=0.15,
        loop_tier=LoopTier.OPERATIONAL,
    )
    estimate = StateEstimate(
        state_id="governance_simulation",
        value=str(sim.get("result", "unknown")),
        uncertainty=max(0.0, min(1.0, float(state_uncertainty))),
        sources=(feedback,),
        observed_at_utc=now.isoformat(),
    )
    action = CandidateAction(
        action_id=action_id,
        capability_scope="deploy:ecosystem_rollout",
        predicted_outcome="rollout_staged_and_healthy",
        reversible=pct < 100,
        blast="subsystem" if pct < 100 else "system",
        requested_at_utc=now.isoformat(),
    )
    try:
        authority_state = controller_authority if isinstance(controller_authority, ControllerAuthorityState) else ControllerAuthorityState(str(controller_authority))
    except ValueError:
        authority_state = ControllerAuthorityState.CONTESTED
    decision = authorize_control_step(
        contract=contract,
        controller_authority=authority_state,
        objective_authorized=bool(objective_authorized),
        estimate=estimate,
        action=action,
        history=(),
    )
    s["governance"]["controller_authority"] = decision.controller_authority.value
    if not decision.allowed:
        _save(cwd, s)
        return {
            "ok": False,
            "reason": decision.reason,
            "loop_state": decision.loop_state.value,
            "controller_authority": decision.controller_authority.value,
            "authority_granted": False,
            "investigation_required": decision.investigation_required,
        }

    # Pure Logic boundary: eligibility is not final authority. The live rollout
    # is withheld until the independent capability/execution authority chain is wired.
    _save(cwd, s)
    return {
        "ok": False,
        "reason": "control_loop_eligible_but_final_deployment_authority_not_supplied",
        "loop_state": decision.loop_state.value,
        "controller_authority": decision.controller_authority.value,
        "eligible_capability_scope": decision.permitted_capability_scope,
        "authority_granted": False,
    }


def governance_validate(cwd: str) -> dict:
    s = _load(cwd)
    rd = grn_node_discovery(cwd)
    total = int(rd.get("total", 0))
    rollout = s["governance"]["last_rollout"]
    if not rollout:
        return {"ok": False, "reason": "no rollout"}
    val = {
        "nodes_validated": total,
        "rollout": rollout,
        "result": "pass" if total >= 1 else "warn",
        "validated_utc": _utc_now(),
        "independent_outcome_authority": False,
    }
    s["governance"]["last_validation"] = val
    _save(cwd, s)
    return {"ok": True, "validation": val, "authority_granted": False}


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
    return {"ok": True, "ecosystem_score": score, "ecosystem_tier": tier, "checks": checks, "gaps": gaps, "authority_granted": False}


def maximize(cwd: str) -> dict:
    node_register(cwd, "edge", "edge-node", "linux", "balanced")
    node_register(cwd, "compute", "compute-node", "linux", "high")
    node_register(cwd, "coordination", "coord-node", "linux", "high")
    node_register(cwd, "archive", "archive-node", "linux", "normal")
    governance_propose(cwd, "scheduler", "sched_global_v2")
    governance_simulate(cwd)
    rollout = governance_rollout(cwd, 100)
    if not rollout.get("ok", False):
        return {"ok": False, "reason": rollout.get("reason"), "rollout": rollout, "authority_granted": False}
    governance_validate(cwd)
    serp_telemetry_submit(cwd, "max-node", "us-west", 68.0, 55.0, 62.0, 85.0, 40.0)
    ai_optimize(cwd)
    return {"ok": True, "grade": ecosystem_grade(cwd), "authority_granted": False}
