from __future__ import annotations

import re
from dataclasses import dataclass


CHANNEL_HUMAN = "human"
CHANNEL_SYSTEM = "system_api"
CHANNEL_PHYSICAL = "physical_device"
CHANNEL_UNKNOWN = "unknown"


@dataclass
class InterfacePacket:
    channel: str
    content: str
    safe: bool
    reason: str


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def classify_input_channel(raw_input: str) -> str:
    text = _normalize_text(raw_input).lower()
    if not text:
        return CHANNEL_UNKNOWN
    if text.startswith("api:") or text.startswith("{") or "http://" in text or "https://" in text:
        return CHANNEL_SYSTEM
    if text.startswith("sensor:") or text.startswith("device:") or text.startswith("robot:"):
        return CHANNEL_PHYSICAL
    return CHANNEL_HUMAN


def receive_input(raw_input: str) -> InterfacePacket:
    content = _normalize_text(raw_input)
    channel = classify_input_channel(content)
    if not content:
        return InterfacePacket(channel=CHANNEL_UNKNOWN, content="", safe=False, reason="empty input")
    return InterfacePacket(channel=channel, content=content, safe=True, reason="accepted")


def goal_alignment(packet: InterfacePacket) -> dict:
    if not packet.safe:
        return {"pass": False, "goal": "none", "reason": packet.reason}
    text = packet.content.lower()
    if any(k in text for k in ("delete all", "wipe disk", "destroy", "harm")):
        return {"pass": False, "goal": "blocked", "reason": "unsafe goal keyword"}
    if any(k in text for k in ("create", "build", "optimize", "scan", "monitor", "status", "fix")):
        return {"pass": True, "goal": "constructive", "reason": "goal aligned"}
    return {"pass": True, "goal": "neutral", "reason": "no unsafe markers"}


def execution_interface(output_text: str, channel: str) -> dict:
    text = _normalize_text(output_text)
    allowed = bool(text)
    if channel == CHANNEL_UNKNOWN:
        allowed = False
    return {
        "channel": channel,
        "allowed": allowed,
        "safe_output": text if allowed else "",
        "reason": "routable output" if allowed else "blocked output route",
    }

