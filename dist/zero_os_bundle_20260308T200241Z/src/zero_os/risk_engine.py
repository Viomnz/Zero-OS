from __future__ import annotations

from pathlib import Path


def classify_risk(action: str, blast_radius: str = "", reversible: bool = True) -> dict:
    action_n = action.strip().lower()
    radius = blast_radius.strip().lower() or "local"
    risk = "low"
    reasons: list[str] = []
    if any(token in action_n for token in ("rollback", "revoke", "quarantine", "restore", "disable", "recover")):
        risk = "high"
        reasons.append("destructive_or_stateful_action")
    elif any(token in action_n for token in ("upgrade", "rotate", "throttle", "restart")):
        risk = "medium"
        reasons.append("service_or_runtime_change")
    if radius in {"system", "global", "multi-region", "fleet"}:
        risk = "high"
        reasons.append("large_blast_radius")
    elif radius in {"stage", "cluster", "service"} and risk == "low":
        risk = "medium"
        reasons.append("shared_scope")
    if not reversible and risk != "high":
        risk = "high"
        reasons.append("irreversible_action")
    return {"risk": risk, "blast_radius": radius, "reasons": reasons}


def autonomous_thresholds() -> dict:
    return {
        "low": 0.72,
        "medium": 0.86,
        "high": 0.96,
    }


def rollback_ready(cwd: str) -> dict:
    base = Path(cwd).resolve()
    indicators = {
        "recovery_snapshot": (base / ".zero_os" / "production" / "snapshots").exists(),
        "native_store_checkpoint": (base / ".zero_os" / "native_store").exists(),
        "state_file": (base / ".zero_os" / "state.json").exists(),
    }
    score = round(sum(1 for v in indicators.values() if v) / max(1, len(indicators)), 4)
    return {"ready": indicators["recovery_snapshot"] and indicators["state_file"], "score": score, "indicators": indicators}
