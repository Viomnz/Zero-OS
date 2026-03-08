from __future__ import annotations

from datetime import datetime, timezone


ALLOWED_TOOLS = {"status", "time"}


def maybe_run_tool(prompt: str) -> dict | None:
    text = str(prompt or "").strip()
    if not text.lower().startswith("tool:"):
        return None
    parts = text.split(":", 2)
    if len(parts) < 2:
        return {"ok": False, "error": "invalid_tool_syntax"}
    tool = parts[1].strip().lower()
    if tool not in ALLOWED_TOOLS:
        return {"ok": False, "error": "tool_not_allowed", "allowed_tools": sorted(ALLOWED_TOOLS)}
    if tool == "status":
        return {"ok": True, "tool": "status", "result": "online"}
    if tool == "time":
        return {"ok": True, "tool": "time", "result": datetime.now(timezone.utc).isoformat()}
    return {"ok": False, "error": "unknown_tool"}
