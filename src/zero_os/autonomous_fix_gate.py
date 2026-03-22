from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from zero_os.action_simulator import simulate_action
from zero_os.confidence_engine import score_confidence
from zero_os.risk_engine import autonomous_thresholds, classify_risk, rollback_ready


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _root(cwd: str) -> Path:
    path = Path(cwd).resolve() / ".zero_os" / "autonomy"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _history_path(cwd: str) -> Path:
    return _root(cwd) / "history.json"


def _load_history(cwd: str) -> dict:
    path = _history_path(cwd)
    if not path.exists():
        data = {"events": []}
        path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        return data
    return json.loads(path.read_text(encoding="utf-8", errors="replace"))


def _save_history(cwd: str, data: dict) -> None:
    _history_path(cwd).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def capture_health_snapshot(cwd: str) -> dict:
    base = Path(cwd).resolve()
    runtime = base / ".zero_os" / "runtime"
    security_report = runtime / "security_report.json"
    recovery_report = runtime / "zero_ai_recovery_report.json"
    state_file = base / ".zero_os" / "state.json"
    native_store_state = base / ".zero_os" / "native_store" / "state.json"
    snapshots = base / ".zero_os" / "production" / "snapshots"
    score = 0
    signals = {
        "state_file": state_file.exists(),
        "recovery_snapshot": snapshots.exists(),
        "runtime_dir": runtime.exists(),
        "security_report": security_report.exists(),
        "recovery_report": recovery_report.exists(),
        "native_store_state": native_store_state.exists(),
    }
    score += 20 if signals["state_file"] else 0
    score += 20 if signals["recovery_snapshot"] else 0
    score += 10 if signals["runtime_dir"] else 0
    score += 20 if signals["security_report"] else 0
    score += 15 if signals["recovery_report"] else 0
    score += 15 if signals["native_store_state"] else 0
    return {
        "time_utc": _utc_now(),
        "health_score": score,
        "signals": signals,
    }


def _delta_quality(before: dict | None, after: dict | None) -> float | None:
    if not before or not after:
        return None
    before_score = float(before.get("health_score", 0.0))
    after_score = float(after.get("health_score", 0.0))
    delta = after_score - before_score
    normalized = 0.5
    if delta > 0:
        normalized = min(1.0, 0.5 + (delta / 100.0))
    elif delta < 0:
        normalized = max(0.0, 0.5 + (delta / 100.0))
    if after_score >= before_score and after_score >= 60:
        normalized = min(1.0, normalized + 0.1)
    return round(normalized, 4)


def _event_quality(event: dict) -> float:
    snapshot_quality = _delta_quality(event.get("health_before"), event.get("health_after"))
    if snapshot_quality is not None:
        return snapshot_quality
    outcome = str(event.get("outcome", "")).lower()
    base = 1.0 if outcome == "success" else 0.0
    rollback_used = bool(event.get("rollback_used", False))
    verification_passed = bool(event.get("verification_passed", outcome == "success"))
    recovery_seconds = float(event.get("recovery_seconds", 0.0) or 0.0)
    blast_radius = str(event.get("blast_radius", "local")).lower()
    blast_penalty = {
        "local": 0.0,
        "service": 0.03,
        "cluster": 0.06,
        "system": 0.1,
        "global": 0.14,
        "multi-region": 0.14,
        "fleet": 0.14,
    }.get(blast_radius, 0.05)
    rollback_penalty = 0.08 if rollback_used else 0.0
    verification_bonus = 0.05 if verification_passed and outcome == "success" else 0.0
    recovery_penalty = min(0.12, recovery_seconds / 600.0 * 0.12) if outcome == "success" else 0.0
    quality = base - blast_penalty - rollback_penalty - recovery_penalty + verification_bonus
    return round(max(0.0, min(1.0, quality)), 4)


def _history_rate(cwd: str, action: str) -> float:
    data = _load_history(cwd)
    relevant = [item for item in data.get("events", []) if item.get("action") == action]
    if not relevant:
        return 0.5
    return round(sum(_event_quality(item) for item in relevant) / len(relevant), 4)


def autonomy_status(cwd: str) -> dict:
    history = _load_history(cwd)
    return {
        "ok": True,
        "history_events": len(history.get("events", [])),
        "thresholds": autonomous_thresholds(),
        "rollback": rollback_ready(cwd),
    }


def autonomy_evaluate(
    cwd: str,
    action: str,
    blast_radius: str,
    reversible: bool,
    evidence_count: int,
    contradictory_signals: int,
    independent_verifiers: int,
    checks: dict[str, bool],
    *,
    planner_confidence: float | None = None,
    planner_risk_level: str | None = None,
    planner_ambiguity_count: int = 0,
) -> dict:
    risk = classify_risk(action, blast_radius=blast_radius, reversible=reversible)
    rollback = rollback_ready(cwd)
    simulation = simulate_action(action, checks, dry_run_supported=True)
    history_rate = _history_rate(cwd, action)
    confidence = score_confidence(
        evidence_count=evidence_count,
        contradictory_signals=contradictory_signals,
        historical_success_rate=history_rate,
        simulation_ok=bool(simulation.get("ok", False)),
        rollback_score=float(rollback.get("score", 0.0)),
        independent_verifiers=independent_verifiers,
    )
    threshold = autonomous_thresholds()[risk["risk"]]
    effective_confidence = float(confidence.get("confidence", 0.0) or 0.0)
    planner_signal = {
        "confidence": None if planner_confidence is None else round(float(planner_confidence), 4),
        "risk_level": str(planner_risk_level or ""),
        "ambiguity_count": int(planner_ambiguity_count or 0),
    }
    if planner_confidence is not None:
        planner_conf = max(0.0, min(1.0, float(planner_confidence)))
        confidence_weight = 0.5 if str(planner_risk_level or risk["risk"]).lower() in {"high", "system", "critical"} else 0.3
        effective_confidence = round(min(effective_confidence, (effective_confidence * (1.0 - confidence_weight)) + (planner_conf * confidence_weight)), 4)
    action_decision = "allow"
    reason = "threshold_met"
    blockers: list[str] = []
    if not rollback.get("ready", False) and risk["risk"] == "high":
        action_decision = "hold_for_review"
        reason = "rollback_not_ready"
        blockers.append("rollback_not_ready")
    elif not simulation.get("ok", False):
        action_decision = "hold_for_review"
        reason = "simulation_failed"
        blockers.extend(simulation.get("failed_checks", []))
    elif planner_confidence is not None and str(planner_risk_level or risk["risk"]).lower() == "high" and float(planner_confidence) < 0.7:
        action_decision = "hold_for_review"
        reason = "planner_confidence_below_high_risk_threshold"
        blockers.append("planner_confidence_below_high_risk_threshold")
    elif planner_confidence is not None and float(planner_confidence) < 0.5 and str(planner_risk_level or risk["risk"]).lower() in {"medium", "high"}:
        action_decision = "hold_for_review"
        reason = "planner_confidence_below_mutation_threshold"
        blockers.append("planner_confidence_below_mutation_threshold")
    elif planner_confidence is not None and int(planner_ambiguity_count or 0) >= 4 and float(planner_confidence) < 0.75:
        action_decision = "hold_for_review"
        reason = "planner_ambiguity_too_high"
        blockers.append("planner_ambiguity_too_high")
    elif effective_confidence < threshold:
        action_decision = "hold_for_review"
        reason = "confidence_below_threshold"
    return {
        "ok": True,
        "action": action,
        "risk": risk,
        "rollback": rollback,
        "simulation": simulation,
        "confidence": confidence,
        "effective_confidence": effective_confidence,
        "planner": planner_signal,
        "decision": action_decision,
        "decision_reason": reason,
        "threshold": threshold,
        "blockers": blockers,
    }


def autonomy_record(
    cwd: str,
    action: str,
    outcome: str,
    confidence: float,
    *,
    rollback_used: bool = False,
    recovery_seconds: float = 0.0,
    blast_radius: str = "local",
    verification_passed: bool | None = None,
    health_before: dict | None = None,
    health_after: dict | None = None,
) -> dict:
    data = _load_history(cwd)
    event = {
        "time_utc": _utc_now(),
        "action": action,
        "outcome": outcome,
        "confidence": float(confidence),
        "rollback_used": bool(rollback_used),
        "recovery_seconds": float(recovery_seconds),
        "blast_radius": blast_radius,
        "verification_passed": bool(verification_passed) if verification_passed is not None else str(outcome).lower() == "success",
        "health_before": health_before or {},
        "health_after": health_after or {},
    }
    event["quality"] = _event_quality(event)
    data.setdefault("events", []).append(event)
    data["events"] = data["events"][-500:]
    _save_history(cwd, data)
    return {"ok": True, "event": event}
