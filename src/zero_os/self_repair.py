from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from zero_os.autonomous_fix_gate import autonomy_record, capture_health_snapshot
from zero_os.authority_runtime_trace import record_event
from zero_os.pure_logic_security_api import monitor_status
from zero_os.cure_firewall_agent import run_cure_firewall_agent
from zero_os.execution_authority_ticket import acknowledge_consumed_execution_ticket
from zero_os.independent_outcome_verifier import OutcomeEvidence, verify_outcome
from zero_os.pure_logic_control_loop import (
    CandidateAction,
    ControllerAuthorityState,
    ControllerContract,
    FeedbackSource,
    LoopTier,
    StateEstimate,
    authorize_control_step,
)
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
        "last_mechanism_ok": None,
        "last_outcome_verified": None,
        "last_actions": [],
        "authority_model": "pure_logic_constitutional_ticket_plus_control_loop_plus_sink_handoff",
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


def _outcome_evidence(readiness_after: dict, triad: dict) -> list[OutcomeEvidence]:
    readiness_score = float(readiness_after.get("score", 0.0) or 0.0)
    triad_ok = bool(triad.get("ok", False))
    triad_balanced = bool((triad.get("report") or {}).get("balanced", False))
    return [
        OutcomeEvidence(
            source_id="runtime_readiness_probe",
            method_family="readiness_state_probe",
            observed_state=f"readiness:{readiness_score}",
            supports_expected=readiness_score >= 60.0,
            lineage=("os_readiness",),
        ),
        OutcomeEvidence(
            source_id="triad_state_probe",
            method_family="triad_runtime_probe",
            observed_state=f"triad_ok:{triad_ok}:balanced:{triad_balanced}",
            supports_expected=triad_ok and triad_balanced,
            lineage=("triad_balance",),
        ),
    ]


def _control_loop_decision(cwd: str, readiness_before: dict) -> object:
    now = datetime.now(timezone.utc)
    triad_before = triad_ops_status(cwd)
    readiness_score = float(readiness_before.get("score", 0.0) or 0.0)
    sources = (
        FeedbackSource(
            source_id="runtime_readiness_probe",
            provenance="os_readiness",
            method_family="readiness_state_probe",
            lineage=("os_readiness",),
            fresh_until_utc=(now + timedelta(seconds=30)).isoformat(),
            demonstrated_scope=("runtime:self_repair",),
            reliability=0.8,
        ),
        FeedbackSource(
            source_id="triad_state_probe",
            provenance="triad_ops_status",
            method_family="triad_runtime_probe",
            lineage=("triad_balance",),
            fresh_until_utc=(now + timedelta(seconds=30)).isoformat(),
            demonstrated_scope=("runtime:self_repair",),
            reliability=0.8,
        ),
    )
    contract = ControllerContract(
        controller_id="self_repair",
        objective_id="runtime_health",
        authority_id="self_repair_controller",
        scope=("runtime:self_repair",),
        allowed_actions=("self_repair",),
        max_blast="system",
        expires_at_utc=(now + timedelta(minutes=5)).isoformat(),
        revocation_conditions=("controller_compromised", "CONTROL_OSCILLATION", "feedback_corrupted"),
        expected_response_min_seconds=1.0,
        expected_response_max_seconds=60.0,
        max_uncertainty_for_irreversible_action=0.15,
        loop_tier=LoopTier.OPERATIONAL,
    )
    estimate = StateEstimate(
        state_id="runtime_health",
        value=f"readiness:{readiness_score}:triad_enabled:{bool(triad_before.get('enabled', False))}",
        uncertainty=0.15 if readiness_score >= 60.0 else 0.35,
        sources=sources,
        observed_at_utc=now.isoformat(),
    )
    action = CandidateAction(
        action_id="self_repair",
        capability_scope="runtime:self_repair",
        predicted_outcome="bounded_runtime_repair_healthy",
        reversible=True,
        blast="system",
        requested_at_utc=now.isoformat(),
    )
    # This is controller eligibility only. Objective/claim/capability authority is
    # still independently enforced by the constitutional ticket path.
    return authorize_control_step(
        contract=contract,
        controller_authority=ControllerAuthorityState.PROVISIONAL,
        objective_authorized=True,
        estimate=estimate,
        action=action,
    )


def _record_outcome_trace(cwd: str, handoff: dict, outcome) -> None:
    ticket = dict(handoff.get("ticket") or {})
    trace_id = str(ticket.get("ticket_id", ""))
    if not trace_id:
        return
    record_event(
        cwd,
        trace_id=trace_id,
        event_kind="outcome_verify",
        principal_id=str(ticket.get("principal_id", "")),
        authority_id=str(ticket.get("authority_id", "")),
        objective_id=str(ticket.get("objective_id", "")),
        action_kind=str(ticket.get("action_kind", "self_repair")),
        subject_id=str(ticket.get("subject_id", "")),
        state_revision=str(ticket.get("state_revision", "")),
        artifact_id=trace_id,
        payload={
            "verified": bool(outcome.verified),
            "status": outcome.status,
            "independent_groups": outcome.independent_groups,
            "contradictions": list(outcome.contradictions),
        },
    )


def self_repair_run(cwd: str) -> dict:
    readiness_before = os_readiness(cwd)
    loop_decision = _control_loop_decision(cwd, readiness_before)
    if not bool(loop_decision.allowed):
        return {
            "ok": False,
            "blocked": True,
            "reason": str(loop_decision.reason),
            "control_loop": {
                "state": loop_decision.loop_state.value,
                "controller_authority": loop_decision.controller_authority.value,
                "authority_reduction": loop_decision.authority_reduction,
            },
            "actions": [],
        }

    handoff = acknowledge_consumed_execution_ticket(cwd, "self_repair", max_handoff_seconds=10)
    if not bool(handoff.get("ok", False)):
        return {
            "ok": False,
            "blocked": True,
            "reason": "constitutional_self_repair_handoff_missing",
            "authority": handoff,
            "control_loop": {
                "state": loop_decision.loop_state.value,
                "controller_authority": loop_decision.controller_authority.value,
                "eligible_only": True,
            },
            "actions": [],
        }

    health_before = capture_health_snapshot(cwd)
    actions: list[str] = []
    authority_requests: list[str] = []
    logic = recovery_decision(cwd, True, readiness_before.get("score", 0) >= 40, "system")

    if readiness_before.get("score", 0) < 100:
        r = apply_missing_fix(cwd)
        if r.get("created_count", 0) > 0:
            actions.append(f"os_missing_fix:{r.get('created_count', 0)}")
        b = apply_beginner_os_fix(cwd)
        if b.get("created_count", 0) > 0:
            actions.append(f"beginner_os_fix:{b.get('created_count', 0)}")

    antivirus_monitor = monitor_status(cwd)
    if not antivirus_monitor.get("enabled", False):
        authority_requests.append("policy_change:enable_antivirus_monitor")

    if not triad_ops_status(cwd).get("enabled", False):
        triad_ops_set(cwd, True, 120, "log+inbox")
        actions.append("triad_ops:on")

    triad = triad_ops_tick(cwd)
    actions.append("triad_ops:tick")

    firewall = run_cure_firewall_agent(cwd, pressure=85, verify=True)
    actions.append("cure_firewall_agent:run")

    readiness_after = os_readiness(cwd)
    mechanism_ok = bool(triad.get("ok", False)) and bool(firewall.get("mechanism_ok", firewall.get("ok", False))) and float(readiness_after.get("score", 0) or 0) >= 60.0
    outcome = verify_outcome(
        actor_id="self_repair",
        expected_state="bounded_runtime_repair_healthy",
        evidence=_outcome_evidence(readiness_after, triad),
        required_independent_groups=2,
    )
    _record_outcome_trace(cwd, handoff, outcome)
    ok = mechanism_ok and outcome.verified

    st = self_repair_status(cwd)
    st["last_tick_utc"] = _utc_now()
    st["last_ok"] = ok
    st["last_mechanism_ok"] = mechanism_ok
    st["last_outcome_verified"] = outcome.verified
    st["last_actions"] = actions
    st["last_authority_requests"] = authority_requests
    st["last_control_loop_state"] = loop_decision.loop_state.value
    st["last_controller_authority"] = loop_decision.controller_authority.value
    _state_path(cwd).write_text(json.dumps(st, indent=2) + "\n", encoding="utf-8")
    autonomy_record(
        cwd,
        "self repair run",
        "success" if ok else "failed",
        float(logic.get("confidence", 0.0)),
        rollback_used=False,
        recovery_seconds=8.0 if ok else 45.0,
        blast_radius="system",
        verification_passed=outcome.verified,
        health_before=health_before,
        health_after=capture_health_snapshot(cwd),
    )

    return {
        "ok": ok,
        "mechanism_ok": mechanism_ok,
        "outcome_verified": outcome.verified,
        "outcome_status": outcome.status,
        "outcome_independent_groups": outcome.independent_groups,
        "outcome_contradictions": list(outcome.contradictions),
        "authority": handoff,
        "control_loop": {
            "state": loop_decision.loop_state.value,
            "controller_authority": loop_decision.controller_authority.value,
            "eligible_only": True,
            "final_authority_granted": False,
        },
        "authority_requests": authority_requests,
        "actions": actions,
        "readiness_before": readiness_before.get("score", 0),
        "readiness_after": readiness_after.get("score", 0),
        "triad_ok": triad.get("ok", False),
        "triad_balanced": triad.get("report", {}).get("balanced", False),
        "smart_logic": logic,
    }


def self_repair_tick(cwd: str) -> dict:
    st = self_repair_status(cwd)
    if not st.get("enabled", False):
        return {"ok": False, "ran": False, "reason": "self repair disabled"}
    out = self_repair_run(cwd)
    if not bool(out.get("ok", False)):
        return {
            "ok": False,
            "ran": False,
            "reason": str(out.get("reason", "self_repair_not_authorized_or_verified")),
            "result": out,
        }
    return {"ok": True, "ran": True, "result": out}
