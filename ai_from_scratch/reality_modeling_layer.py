from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _runtime(cwd: str) -> Path:
    p = Path(cwd).resolve() / ".zero_os" / "runtime"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _path(cwd: str) -> Path:
    return _runtime(cwd) / "reality_world_model.json"


def _entities(text: str) -> list[dict]:
    tokens = re.findall(r"[A-Za-z0-9_\\-]{3,}", text)
    common = {"the", "and", "with", "from", "that", "this", "have", "into", "for", "zero", "system"}
    out = []
    seen = set()
    for t in tokens:
        k = t.lower()
        if k in common or k in seen:
            continue
        seen.add(k)
        out.append({"id": k, "label": t})
        if len(out) >= 24:
            break
    return out


def update_reality_model(cwd: str, prompt: str, channel: str, context: dict, knowledge: dict) -> dict:
    p = _path(cwd)
    if p.exists():
        data = json.loads(p.read_text(encoding="utf-8", errors="replace"))
    else:
        data = {
            "schema_version": 1,
            "entity_registry": [],
            "relationship_graph": [],
            "state_tracker": {"last_channel": "", "last_prompt": "", "updates": 0},
            "causal_engine": {"rules": [], "last_inference": ""},
            "history": [],
        }

    prompt = str(prompt or "")
    channel = str(channel or "unknown")
    entities = _entities(prompt + " " + str(knowledge.get("unified_text", "")))
    existing = {e.get("id"): e for e in data.get("entity_registry", []) if isinstance(e, dict)}
    for e in entities:
        existing[e["id"]] = e
    entity_registry = list(existing.values())

    relationship_graph = data.get("relationship_graph", [])
    if len(entities) >= 2:
        relationship_graph.append(
            {
                "src": entities[0]["id"],
                "dst": entities[1]["id"],
                "type": "co_observed",
                "time_utc": _utc_now(),
            }
        )
    relationship_graph = relationship_graph[-200:]

    causal = data.get("causal_engine", {})
    causal["last_inference"] = f"channel={channel}; entities={len(entities)}"
    if "rules" not in causal or not isinstance(causal["rules"], list):
        causal["rules"] = []
    if not causal["rules"]:
        causal["rules"] = [
            "if state changes then update relationships",
            "if repeated co_observed then increase confidence",
        ]

    state = data.get("state_tracker", {})
    state["last_channel"] = channel
    state["last_prompt"] = prompt[:280]
    state["updates"] = int(state.get("updates", 0)) + 1
    state["last_context_mode"] = str(context.get("reasoning_parameters", {}).get("priority_mode", "normal"))

    history = data.get("history", [])
    history.append(
        {
            "time_utc": _utc_now(),
            "channel": channel,
            "entity_count": len(entities),
            "prompt_excerpt": prompt[:140],
        }
    )
    history = history[-120:]

    out = {
        "schema_version": 1,
        "entity_registry": entity_registry,
        "relationship_graph": relationship_graph,
        "state_tracker": state,
        "causal_engine": causal,
        "history": history,
    }
    p.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    return {
        "ok": True,
        "entity_count": len(entity_registry),
        "relationship_count": len(relationship_graph),
        "state_updates": state["updates"],
        "causal_last_inference": causal["last_inference"],
        "path": str(p),
    }

