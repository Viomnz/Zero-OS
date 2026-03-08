from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _runtime(cwd: str) -> Path:
    p = Path(cwd).resolve() / ".zero_os" / "runtime"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _load(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return default


def _save(path: Path, payload) -> None:
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _risk_drift(signal_type: str, safe_state: dict, learning_score: float) -> float:
    risk = 0.2
    if signal_type == "negative":
        risk += 0.45
    if safe_state.get("enter_safe_state", False):
        risk += 0.25
    if learning_score < 0.5:
        risk += 0.15
    return round(min(1.0, risk), 4)


def update_long_horizon_strategy(
    cwd: str,
    prompt: str,
    context: dict,
    feedback: dict,
    safe_state: dict,
) -> dict:
    path = _runtime(cwd) / "long_horizon_strategy.json"
    data = _load(
        path,
        {"goals": [], "reviews": [], "stats": {"updates": 0, "high_risk_updates": 0}, "last": {}},
    )

    now = _utc_now()
    learning_score = float(feedback.get("learning_score", 0.0))
    signal_type = str(feedback.get("signal_type", "neutral")).lower()
    risk = _risk_drift(signal_type, safe_state, learning_score)
    horizon_plan = {
        "h30d": (now + timedelta(days=30)).isoformat(),
        "h180d": (now + timedelta(days=180)).isoformat(),
        "h730d": (now + timedelta(days=730)).isoformat(),
    }
    review_days = 7 if risk >= 0.6 else 14 if risk >= 0.35 else 30
    entry = {
        "time_utc": now.isoformat(),
        "goal": str(prompt).strip(),
        "context_mode": str(context.get("reasoning_parameters", {}).get("priority_mode", "normal")),
        "learning_score": learning_score,
        "signal_type": signal_type,
        "risk_drift": risk,
        "milestones": horizon_plan,
        "next_review_utc": (now + timedelta(days=review_days)).isoformat(),
    }

    goals = list(data.get("goals", []))
    goals.append(entry)
    data["goals"] = goals[-500:]
    reviews = list(data.get("reviews", []))
    reviews.append({"time_utc": now.isoformat(), "goal": entry["goal"], "next_review_utc": entry["next_review_utc"]})
    data["reviews"] = reviews[-500:]
    stats = data.get("stats", {"updates": 0, "high_risk_updates": 0})
    stats["updates"] = int(stats.get("updates", 0)) + 1
    if risk >= 0.6:
        stats["high_risk_updates"] = int(stats.get("high_risk_updates", 0)) + 1
    data["stats"] = stats
    data["last"] = entry
    _save(path, data)

    return {
        "ok": True,
        "risk_drift": risk,
        "next_review_utc": entry["next_review_utc"],
        "milestones": horizon_plan,
        "stats": stats,
    }
