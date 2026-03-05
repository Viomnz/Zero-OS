from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


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


def _norm(text: str) -> str:
    return " ".join(str(text or "").strip().lower().split())


def update_memory_layer(
    cwd: str,
    prompt: str,
    context: dict,
    knowledge: dict,
    feedback: dict,
    adaptation: dict,
    evolution: dict,
) -> dict:
    rt = _runtime(cwd)
    path = rt / "memory_update_layer.json"
    data = _load(
        path,
        {
            "short_term": [],
            "long_term": [],
            "episodic": [],
            "procedural": [],
            "revisions": [],
            "stats": {"writes": 0, "conflicts": 0, "dedup": 0},
        },
    )

    unified_text = str(knowledge.get("unified_model", {}).get("unified_text", prompt)).strip() or str(prompt)
    key = _norm(unified_text)
    signal_type = str(feedback.get("signal_type", "neutral"))
    learning_score = float(feedback.get("learning_score", 0.0))

    short_entry = {
        "time_utc": _utc_now(),
        "prompt": str(prompt),
        "context_mode": str(context.get("reasoning_parameters", {}).get("priority_mode", "normal")),
        "signal_type": signal_type,
    }
    episodic_entry = {
        "time_utc": _utc_now(),
        "event": "decision_cycle",
        "prompt": str(prompt),
        "learning_score": learning_score,
        "adapt_mode": str(adaptation.get("mode", "moderate")),
    }
    procedural_entry = {
        "time_utc": _utc_now(),
        "strategy": {
            "set_profile": adaptation.get("actions", {}).get("set_profile"),
            "set_mode": adaptation.get("actions", {}).get("set_mode"),
            "evolution_method": evolution.get("action", {}).get("method"),
        },
    }

    existing = {str(x.get("key", "")): x for x in data.get("long_term", []) if isinstance(x, dict)}
    conflict = key in existing and str(existing[key].get("value", "")).strip() != unified_text.strip()
    if conflict:
        data["stats"]["conflicts"] = int(data["stats"].get("conflicts", 0)) + 1
        existing[key]["replaced_by"] = unified_text
        existing[key]["updated_utc"] = _utc_now()
    else:
        if key not in existing:
            existing[key] = {"key": key, "value": unified_text, "created_utc": _utc_now(), "priority": "normal"}
        else:
            data["stats"]["dedup"] = int(data["stats"].get("dedup", 0)) + 1
            existing[key]["updated_utc"] = _utc_now()

    if learning_score >= 0.8 and signal_type == "positive":
        existing[key]["priority"] = "high"
    elif signal_type == "negative":
        existing[key]["priority"] = "review"

    data["long_term"] = list(existing.values())[-1200:]
    data["short_term"] = (list(data.get("short_term", [])) + [short_entry])[-80:]
    data["episodic"] = (list(data.get("episodic", [])) + [episodic_entry])[-500:]
    data["procedural"] = (list(data.get("procedural", [])) + [procedural_entry])[-500:]
    data["revisions"] = (
        list(data.get("revisions", []))
        + [
            {
                "time_utc": _utc_now(),
                "key": key,
                "conflict": conflict,
                "signal_type": signal_type,
                "learning_score": learning_score,
            }
        ]
    )[-1200:]
    data["stats"]["writes"] = int(data["stats"].get("writes", 0)) + 1
    data["last"] = {
        "time_utc": _utc_now(),
        "key": key,
        "conflict": conflict,
        "priority": existing[key].get("priority", "normal"),
    }
    _save(path, data)

    return {
        "ok": True,
        "key": key,
        "conflict_detected": conflict,
        "priority": existing[key].get("priority", "normal"),
        "sizes": {
            "short_term": len(data["short_term"]),
            "long_term": len(data["long_term"]),
            "episodic": len(data["episodic"]),
            "procedural": len(data["procedural"]),
            "revisions": len(data["revisions"]),
        },
        "stats": data["stats"],
    }
