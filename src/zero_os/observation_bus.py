from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Iterable

from zero_os.state_registry import boot_state_registry, get_state_store


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stream_default() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "updated_utc": _utc_now(),
        "source_cycle": "",
        "event_count": 0,
        "blocking_event_count": 0,
        "warning_event_count": 0,
        "error_event_count": 0,
        "domains": [],
        "latest_by_domain": {},
        "recent": [],
    }


def emit_observation(
    *,
    domain: str,
    name: str,
    value: Any,
    source: str,
    confidence: float = 1.0,
    blocking: bool = False,
    severity: str = "info",
    depends_on: Iterable[str] | None = None,
    affects: Iterable[str] | None = None,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "time_utc": _utc_now(),
        "domain": str(domain),
        "name": str(name),
        "value": deepcopy(value),
        "source": str(source),
        "confidence": max(0.0, min(1.0, float(confidence))),
        "blocking": bool(blocking),
        "severity": str(severity or "info"),
        "depends_on": list(depends_on or []),
        "affects": list(affects or []),
        "details": deepcopy(details or {}),
    }


def build_observation_stream(
    current: dict[str, Any] | None,
    observations: Iterable[dict[str, Any]],
    *,
    source_cycle: str = "",
    max_events: int = 64,
) -> dict[str, Any]:
    payload = dict(current or _stream_default())
    recent = [dict(item or {}) for item in list(payload.get("recent", [])) if isinstance(item, dict)]
    next_events = [dict(item or {}) for item in list(observations or []) if isinstance(item, dict)]
    recent.extend(next_events)
    trimmed = recent[-max(1, int(max_events)) :]
    latest_by_domain: dict[str, dict[str, Any]] = {}
    for item in trimmed:
        domain = str(item.get("domain", "") or "").strip()
        if domain:
            latest_by_domain[domain] = {
                "name": str(item.get("name", "") or ""),
                "severity": str(item.get("severity", "info") or "info"),
                "blocking": bool(item.get("blocking", False)),
                "time_utc": str(item.get("time_utc", "") or ""),
            }
    payload.update(
        {
            "schema_version": 1,
            "updated_utc": _utc_now(),
            "source_cycle": str(source_cycle or ""),
            "event_count": len(trimmed),
            "blocking_event_count": sum(1 for item in trimmed if bool(item.get("blocking", False))),
            "warning_event_count": sum(1 for item in trimmed if str(item.get("severity", "")) == "warning"),
            "error_event_count": sum(1 for item in trimmed if str(item.get("severity", "")) == "error"),
            "domains": sorted({str(item.get("domain", "")) for item in trimmed if str(item.get("domain", ""))}),
            "latest_by_domain": latest_by_domain,
            "recent": trimmed,
        }
    )
    return payload


def observation_stream_status(cwd: str) -> dict[str, Any]:
    boot_state_registry(cwd, names=["observation_stream"])
    payload = dict(get_state_store(cwd, "observation_stream", _stream_default()) or {})
    if not payload:
        payload = _stream_default()
    payload.setdefault("ok", True)
    payload.setdefault("schema_version", 1)
    payload.setdefault("updated_utc", _utc_now())
    payload.setdefault("recent", [])
    payload.setdefault("latest_by_domain", {})
    payload.setdefault("domains", [])
    payload.setdefault("event_count", len(list(payload.get("recent", []))))
    return payload


def observation_summary(observations: Iterable[dict[str, Any]]) -> dict[str, Any]:
    items = [dict(item or {}) for item in observations]
    return {
        "count": len(items),
        "blocking_count": sum(1 for item in items if bool(item.get("blocking", False))),
        "warning_count": sum(1 for item in items if str(item.get("severity", "")) == "warning"),
        "error_count": sum(1 for item in items if str(item.get("severity", "")) == "error"),
        "domains": sorted({str(item.get("domain", "")) for item in items if str(item.get("domain", ""))}),
    }
