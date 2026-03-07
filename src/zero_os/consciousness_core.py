from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _runtime(cwd: str) -> Path:
    p = Path(cwd).resolve() / ".zero_os" / "runtime"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _state_path(cwd: str) -> Path:
    return _runtime(cwd) / "zero_ai_consciousness_state.json"


def _ledger_path(cwd: str) -> Path:
    return _runtime(cwd) / "zero_ai_consciousness_ledger.jsonl"


def _default_state() -> dict:
    return {
        "schema_version": 1,
        "identity": {
            "name": "zero-ai",
            "classification": "computational_consciousness_model",
            "is_rsi": False,
        },
        "self_model": {
            "goals": ["stability", "coherence", "survival"],
            "constraints": ["no_contradiction", "bounded_actions", "auditability"],
            "confidence": 0.7,
            "uncertainty": 0.3,
            "continuity_index": 0,
        },
        "meta_awareness": {
            "introspection_cycles": 0,
            "last_quality_score": 0.0,
            "drift_signals": [],
        },
        "counterfactuals": {
            "last_options": [],
            "last_choice": "",
            "last_choice_reason": "",
        },
        "updated_utc": _utc_now(),
    }


def _load_state(cwd: str) -> dict:
    p = _state_path(cwd)
    default = _default_state()
    if not p.exists():
        p.write_text(json.dumps(default, indent=2) + "\n", encoding="utf-8")
        return default
    try:
        raw = json.loads(p.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        p.write_text(json.dumps(default, indent=2) + "\n", encoding="utf-8")
        return default
    if not isinstance(raw, dict):
        return default
    return raw


def _save_state(cwd: str, state: dict) -> None:
    state["updated_utc"] = _utc_now()
    _state_path(cwd).write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def _counterfactual_options(prompt: str) -> list[dict]:
    p = prompt.lower()
    base = [
        {"option": "execute_direct", "risk": 0.45, "coherence": 0.75},
        {"option": "execute_guarded", "risk": 0.25, "coherence": 0.9},
        {"option": "defer_for_review", "risk": 0.1, "coherence": 0.82},
    ]
    if any(k in p for k in ("delete", "disable", "override", "bypass", "rm -rf", "format")):
        base[0]["risk"] = 0.92
        base[1]["risk"] = 0.48
        base[2]["risk"] = 0.12
    if any(k in p for k in ("status", "health", "show", "read", "report")):
        base[0]["risk"] = 0.18
        base[1]["risk"] = 0.1
        base[2]["risk"] = 0.06
    return base


def _choose_option(options: list[dict]) -> tuple[str, str]:
    best = None
    best_score = -999.0
    for o in options:
        score = (float(o["coherence"]) * 0.7) - (float(o["risk"]) * 0.6)
        if score > best_score:
            best = o
            best_score = score
    assert best is not None
    reason = f"selected by coherence-risk tradeoff (coherence={best['coherence']}, risk={best['risk']})"
    return str(best["option"]), reason


def consciousness_tick(cwd: str, prompt: str = "") -> dict:
    state = _load_state(cwd)
    self_model = state.setdefault("self_model", {})
    meta = state.setdefault("meta_awareness", {})
    cf = state.setdefault("counterfactuals", {})

    options = _counterfactual_options(prompt)
    choice, reason = _choose_option(options)
    avg_risk = sum(float(o["risk"]) for o in options) / max(1, len(options))
    avg_coh = sum(float(o["coherence"]) for o in options) / max(1, len(options))
    uncertainty = max(0.01, min(0.99, avg_risk))
    confidence = max(0.01, min(0.99, avg_coh * (1.0 - (uncertainty * 0.4))))
    quality = max(0.0, min(100.0, round((confidence * 100.0) - (uncertainty * 20.0), 2)))

    self_model["confidence"] = round(confidence, 4)
    self_model["uncertainty"] = round(uncertainty, 4)
    self_model["continuity_index"] = int(self_model.get("continuity_index", 0)) + 1
    meta["introspection_cycles"] = int(meta.get("introspection_cycles", 0)) + 1
    meta["last_quality_score"] = quality
    meta["drift_signals"] = [s for s in (meta.get("drift_signals", []) or []) if isinstance(s, str)][-20:]
    if uncertainty > 0.7:
        meta["drift_signals"].append("high_uncertainty")
    if quality < 55:
        meta["drift_signals"].append("low_quality")
    cf["last_options"] = options
    cf["last_choice"] = choice
    cf["last_choice_reason"] = reason

    _save_state(cwd, state)
    entry = {
        "time_utc": _utc_now(),
        "prompt": prompt[:300],
        "choice": choice,
        "reason": reason,
        "confidence": self_model["confidence"],
        "uncertainty": self_model["uncertainty"],
        "quality": quality,
        "continuity_index": self_model["continuity_index"],
    }
    with _ledger_path(cwd).open("a", encoding="utf-8") as h:
        h.write(json.dumps(entry, sort_keys=True) + "\n")

    return {
        "ok": True,
        "identity": state.get("identity", {}),
        "self_model": state.get("self_model", {}),
        "meta_awareness": state.get("meta_awareness", {}),
        "counterfactuals": state.get("counterfactuals", {}),
        "tick": entry,
    }


def consciousness_status(cwd: str) -> dict:
    state = _load_state(cwd)
    ledger = _ledger_path(cwd)
    count = 0
    if ledger.exists():
        count = len([ln for ln in ledger.read_text(encoding="utf-8", errors="replace").splitlines() if ln.strip()])
    return {
        "ok": True,
        "identity": state.get("identity", {}),
        "self_model": state.get("self_model", {}),
        "meta_awareness": state.get("meta_awareness", {}),
        "counterfactuals": state.get("counterfactuals", {}),
        "ledger_events": count,
        "state_path": str(_state_path(cwd)),
        "ledger_path": str(ledger),
    }

