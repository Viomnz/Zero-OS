from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from zero_os.autonomous_fix_gate import autonomy_evaluate, autonomy_record, capture_health_snapshot
from zero_os.antivirus import monitor_set
from zero_os.cure_firewall_agent import run_cure_firewall_agent
from zero_os.readiness import apply_beginner_os_fix, apply_missing_fix, os_readiness
from zero_os.runtime_smart_logic import recovery_decision
from zero_os.triad_balance import triad_ops_set, triad_ops_status, triad_ops_tick


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _state_path(cwd: str) -> Path:
    p = Path(cwd).resolve() / ".zero_os" / "runtime" / "self_repair_state.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def self_repair_status(cwd: str) -> dict:
    default = {
        "enabled": False,
        "interval_seconds": 180,
        "last_tick_utc": "",
        "last_ok": None,
        "last_actions": [],
        "last_authority": {},
    }
    p = _state_path(cwd)
    if not p.exists():
        p.write_text(json.dumps(default, indent=2) + "\n", encoding="utf-8")
        return default
    try:
        data = json.loads(p.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        data = dict(default)
    for k, v in default.items():
        data.setdefault(k, v)
    p.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return data


def self_repair_set(cwd: str, enabled: bool, interval_seconds: int | None = None) -> dict:
    st = self_repair_status(cwd)
    st["enabled"] = bool(enabled)
    if interval_seconds is not None:
        st["interval_seconds"] = max(30, min(3600, int(interval_seconds)))
    _state_path(cwd).write_text(json.dumps(st, indent=2) + "\n", encoding="utf-8")
    return st


def self_repair_run(cwd: str, *, authority_evidence: list[dict] | None = None) -> dict:
    """Run self repair only after independent scope certification.

    Legacy callers that provide no authority evidence are intentionally held for
    review rather than receiving mutation rights from confidence or readiness.
    """
    health_before = capture_health_snapshot(cwd)
    readiness_before = os_readiness(cwd)
    logic = recovery_decision(cwd, True, readiness_before.get("score", 0) >= 40, "system")

    gate = autonomy_evaluate(
        cwd,
        action="self repair run",
        blast_radius="system",
        reversible=True,
        evidence_count=len(authority_evidence or []),
        contradictory_signals=0,
        independent_verifiers=len({str(item.get("independent_group", "")) for item in (authority_evidence or []) if item.get("independent_group")}),
        checks={
            "readiness_observed": readiness_before.get("score", 0) >= 0,
            "health_snapshot_available": bool(health_before),
        },
        planner_confidence=float(logic.get("confidence", 0.0) or 0.0),
        planner_risk_level="high",
        planner_execution_mode="safe",
        planner_strategy="self_repair",
        authority_evidence=list(authority_evidence or []),
        proposer_source="self_repair",
    )

    if gate.get("decision") != "allow":
        st = self_repair_status(cwd)
        st["last_tick_utc"] = _utc_now()
        st["last_ok"] = False
        st["last_actions"] = []
        st["last_authority"] = dict(gate.get("authority") or {})
        _state_path(cwd).write_text(json.dumps(st, indent=2) + "\n", encoding="utf-8")
        return {
            "ok": False,
            "blocked": True,
            "reason": gate.get("decision_reason", "authority_missing"),
            "actions": [],
            "readiness_before": readiness_before.get("score", 0),
            "smart_logic": logic,
            "authority_gate": gate,
        }

    actions: list[str] = []
    if readiness_before.get("score", 0) < 100:
        r = apply_missing_fix(cwd)
        if r.get("created_count", 0) > 0:
            actions.append(f"os_missing_fix:{r.get('created_count', 0)}")
        b = apply_beginner_os_fix(cwd)
        if b.get("created_count", 0) > 0:
            actions.append(f"beginner_os_fix:{b.get('created_count', 0)}")

    monitor_set(cwd, True, 120)
    actions.append("antivirus_monitor:on")

    if not triad_ops_status(cwd).get("enabled", False):
        triad_ops_set(cwd, True, 120, "log+inbox")
        actions.append("triad_ops:on")

    triad = triad_ops_tick(cwd)
    actions.append("triad_ops:tick")

    run_cure_firewall_agent(cwd, pressure=85, verify=True)
    actions.append("cure_firewall_agent:run")

    readiness_after = os_readiness(cwd)
    ok = bool(triad.get("ok", False)) and readiness_after.get("score", 0) >= 60

    st = self_repair_status(cwd)
    st["last_tick_utc"] = _utc_now()
    st["last_ok"] = ok
    st["last_actions"] = actions
    st["last_authority"] = dict(gate.get("authority") or {})
    _state_path(cwd).write_text(json.dumps(st, indent=2) + "\n", encoding="utf-8")
    autonomy_record(
        cwd,
        "self repair run",
        "success" if ok else "failed",
        float(logic.get("confidence", 0.0)),
        rollback_used=False,
        recovery_seconds=8.0 if ok else 45.0,
        blast_radius="system",
        verification_passed=ok,
        health_before=health_before,
        health_after=capture_health_snapshot(cwd),
    )

    return {
        "ok": ok,
        "blocked": False,
        "actions": actions,
        "readiness_before": readiness_before.get("score", 0),
        "readiness_after": readiness_after.get("score", 0),
        "triad_ok": triad.get("ok", False),
        "triad_balanced": triad.get("report", {}).get("balanced", False),
        "smart_logic": logic,
        "authority_gate": gate,
    }


def self_repair_tick(cwd: str, *, authority_evidence: list[dict] | None = None) -> dict:
    st = self_repair_status(cwd)
    if not st.get("enabled", False):
        return {"ok": False, "ran": False, "reason": "self repair disabled"}
    out = self_repair_run(cwd, authority_evidence=authority_evidence)
    return {"ok": bool(out.get("ok", False)), "ran": not bool(out.get("blocked", False)), "result": out}
