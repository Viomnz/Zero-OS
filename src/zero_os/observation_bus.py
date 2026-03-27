from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Iterable


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


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


def observation_summary(observations: Iterable[dict[str, Any]]) -> dict[str, Any]:
    items = [dict(item or {}) for item in observations]
    return {
        "count": len(items),
        "blocking_count": sum(1 for item in items if bool(item.get("blocking", False))),
        "warning_count": sum(1 for item in items if str(item.get("severity", "")) == "warning"),
        "error_count": sum(1 for item in items if str(item.get("severity", "")) == "error"),
        "domains": sorted({str(item.get("domain", "")) for item in items if str(item.get("domain", ""))}),
    }
