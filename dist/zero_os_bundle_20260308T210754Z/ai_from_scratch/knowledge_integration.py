from __future__ import annotations

import json
import re
from pathlib import Path


def _runtime(cwd: str) -> Path:
    p = Path(cwd).resolve() / ".zero_os" / "runtime"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _extract_sources(prompt: str, channel: str) -> list[dict]:
    text = _normalize_text(prompt)
    sources = [{"source": "input_text", "type": "prompt", "content": text}]
    if channel == "system_api":
        sources.append({"source": "external_system", "type": "api_channel", "content": text})
    elif channel == "physical_device":
        sources.append({"source": "sensor_stream", "type": "device_channel", "content": text})
    else:
        sources.append({"source": "human_interface", "type": "human_channel", "content": text})
    return sources


def _resolve_conflicts(sources: list[dict]) -> dict:
    normalized = [_normalize_text(s.get("content", "")) for s in sources]
    unique = []
    for n in normalized:
        if n and n not in unique:
            unique.append(n)
    conflict = len(unique) > 1
    # Conservative resolution: prioritize explicit input_text, then longest remaining.
    selected = ""
    for src in sources:
        if src.get("source") == "input_text":
            selected = _normalize_text(src.get("content", ""))
            break
    if not selected and unique:
        selected = sorted(unique, key=len, reverse=True)[0]
    return {"conflict_detected": conflict, "resolved_text": selected, "variants": unique}


def integrate_knowledge(cwd: str, prompt: str, channel: str) -> dict:
    sources = _extract_sources(prompt, channel)
    conflict = _resolve_conflicts(sources)
    unified_model = {
        "unified_text": conflict["resolved_text"],
        "source_count": len(sources),
        "conflict_detected": conflict["conflict_detected"],
        "variants": conflict["variants"],
    }
    store = {
        "last": unified_model,
        "sources": sources,
    }
    (_runtime(cwd) / "knowledge_model.json").write_text(json.dumps(store, indent=2) + "\n", encoding="utf-8")
    return {
        "ok": True,
        "normalized": _normalize_text(prompt),
        "sources": sources,
        "conflict_resolution": conflict,
        "unified_model": unified_model,
    }

