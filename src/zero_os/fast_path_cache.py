from __future__ import annotations

import threading
import time
from copy import deepcopy
from typing import Any, Callable

_LOCK = threading.RLock()
_CACHE: dict[str, dict[str, dict[str, Any]]] = {}


def cached_compute(
    namespace: str,
    key: str,
    signature: Any,
    compute: Callable[[], Any],
    *,
    ttl_seconds: float | None = None,
) -> tuple[Any, dict[str, Any]]:
    def resolve_signature() -> Any:
        return signature() if callable(signature) else signature

    now = time.time()
    resolved_signature = resolve_signature()
    with _LOCK:
        entry = dict((_CACHE.get(str(namespace)) or {}).get(str(key)) or {})
        if entry and entry.get("signature") == resolved_signature:
            age_seconds = max(0.0, now - float(entry.get("stored_at", now) or now))
            if ttl_seconds is None or age_seconds <= float(ttl_seconds):
                return (
                    deepcopy(entry.get("value")),
                    {
                        "hit": True,
                        "age_seconds": round(age_seconds, 3),
                        "ttl_seconds": ttl_seconds,
                    },
                )

    value = compute()
    stored_signature = resolve_signature()
    with _LOCK:
        namespace_cache = _CACHE.setdefault(str(namespace), {})
        namespace_cache[str(key)] = {
            "signature": deepcopy(stored_signature),
            "value": deepcopy(value),
            "stored_at": now,
        }
    return deepcopy(value), {"hit": False, "age_seconds": 0.0, "ttl_seconds": ttl_seconds}


def clear_fast_path_cache(*, namespace: str = "") -> None:
    with _LOCK:
        if namespace:
            _CACHE.pop(str(namespace), None)
            return
        _CACHE.clear()
