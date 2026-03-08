from __future__ import annotations

import json
from pathlib import Path


DEFAULT_RELIABILITY = {"logic": 1.0, "environment": 1.0, "survival": 1.0}
MIN_RELIABILITY = {"logic": 0.55, "environment": 0.45, "survival": 0.55}


def _path(cwd: str) -> Path:
    p = Path(cwd).resolve() / ".zero_os" / "runtime" / "signal_reliability.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _load(cwd: str) -> dict:
    p = _path(cwd)
    if not p.exists():
        return {"history": [], "current": dict(DEFAULT_RELIABILITY)}
    try:
        raw = json.loads(p.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {"history": [], "current": dict(DEFAULT_RELIABILITY)}
    return {
        "history": list(raw.get("history", []))[-400:],
        "current": dict(raw.get("current", DEFAULT_RELIABILITY)),
    }


def _save(cwd: str, data: dict) -> None:
    _path(cwd).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def evaluate_signal_reliability(cwd: str) -> dict:
    data = _load(cwd)
    cur = data["current"]
    status = {
        "logic": float(cur.get("logic", 1.0)),
        "environment": float(cur.get("environment", 1.0)),
        "survival": float(cur.get("survival", 1.0)),
    }
    degraded = {k: v < MIN_RELIABILITY[k] for k, v in status.items()}
    healthy = not any(degraded.values())
    actions = {
        "recalibrate_logic": degraded["logic"],
        "recalibrate_environment": degraded["environment"],
        "recalibrate_survival": degraded["survival"],
        "allow_execution": healthy or (status["logic"] >= 0.45 and status["survival"] >= 0.45),
    }
    out = {"status": status, "degraded": degraded, "healthy": healthy, "actions": actions}
    data["last_eval"] = out
    _save(cwd, data)
    return out


def update_signal_reliability(cwd: str, critics: dict) -> dict:
    data = _load(cwd)
    cur = data["current"]
    logic = float(critics.get("logic", {}).get("confidence", 0.0))
    env = float(critics.get("environment", {}).get("confidence", 0.0))
    survival = float(critics.get("survival", {}).get("confidence", 0.0))

    # EMA update for smooth reliability adaptation.
    alpha = 0.2
    cur["logic"] = round((1 - alpha) * float(cur.get("logic", 1.0)) + alpha * logic, 4)
    cur["environment"] = round((1 - alpha) * float(cur.get("environment", 1.0)) + alpha * env, 4)
    cur["survival"] = round((1 - alpha) * float(cur.get("survival", 1.0)) + alpha * survival, 4)

    data["current"] = cur
    data["history"].append({"logic": logic, "environment": env, "survival": survival})
    data["history"] = data["history"][-300:]
    _save(cwd, data)
    return {"current": cur}


def apply_reliability_calibration(cwd: str, targets: dict, strength: float = 0.15) -> dict:
    data = _load(cwd)
    cur = data["current"]
    s = max(0.0, min(1.0, float(strength)))
    for key in ("logic", "environment", "survival"):
        current_val = float(cur.get(key, 1.0))
        target_val = float(targets.get(key, current_val))
        cur[key] = round((1.0 - s) * current_val + s * target_val, 4)
    data["current"] = cur
    data["calibration"] = {"targets": {k: float(targets.get(k, cur[k])) for k in ("logic", "environment", "survival")}, "strength": s}
    _save(cwd, data)
    return {"current": cur, "strength": s}
