from __future__ import annotations

import re


def extract_intent(request: str) -> dict:
    text = request.strip()
    lowered = text.lower()
    intent = "observe"
    entities: dict[str, str] = {}
    constraints: dict[str, str] = {}
    goal = text
    if "http://" in lowered or "https://" in lowered:
        intent = "web"
        match = re.search(r"(https?://\S+)", text)
        if match:
            entities["url"] = match.group(1)
    if "store status" in lowered:
        intent = "store_status"
    install_match = re.search(r"install\s+app\s+([a-z0-9._-]+)", lowered)
    if install_match:
        intent = "store_install"
        entities["app"] = install_match.group(1)
    if any(token in lowered for token in ("recover", "recovery")):
        intent = "recover"
    elif any(token in lowered for token in ("repair", "self repair")):
        intent = "self_repair"
    elif any(token in lowered for token in ("status", "diagnostic", "health", "check")):
        intent = "status"
    elif any(token in lowered for token in ("tools", "capabilities")):
        intent = "tools"
    if "safe" in lowered:
        constraints["safety"] = "high"
    if "quick" in lowered or "fast" in lowered:
        constraints["speed"] = "high"
    if "resume" in lowered:
        constraints["resume"] = "true"
    if "approval" in lowered or "approve" in lowered:
        constraints["approval"] = "true"
    if "browser" in lowered:
        entities["channel"] = "browser"
    return {"intent": intent, "entities": entities, "constraints": constraints, "goal": goal, "raw": text}
