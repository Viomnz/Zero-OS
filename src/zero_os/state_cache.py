from __future__ import annotations

import json
import threading
import time
from copy import deepcopy
from pathlib import Path
from typing import Any


_LOCK = threading.RLock()
_JSON_CACHE: dict[str, dict[str, Any]] = {}
_PENDING_JSON_WRITES: dict[str, dict[str, Any]] = {}
_METRICS = {
    "json_cache_hit_count": 0,
    "json_cache_miss_count": 0,
    "json_disk_read_count": 0,
    "json_disk_write_count": 0,
    "json_flush_count": 0,
}


def _path_key(path: Path | str) -> tuple[str, Path]:
    resolved = Path(path).resolve()
    return str(resolved), resolved


def load_json_state(path: Path | str, default: Any) -> Any:
    key, resolved = _path_key(path)
    with _LOCK:
        pending = _PENDING_JSON_WRITES.get(key)
        if pending is not None:
            _METRICS["json_cache_hit_count"] += 1
            return deepcopy(pending["payload"])

    try:
        stat = resolved.stat()
    except OSError:
        return deepcopy(default)

    with _LOCK:
        cached = _JSON_CACHE.get(key)
        if cached and int(cached.get("mtime_ns", -1)) == int(stat.st_mtime_ns) and int(cached.get("size", -1)) == int(stat.st_size):
            _METRICS["json_cache_hit_count"] += 1
            return deepcopy(cached["payload"])

    try:
        payload = json.loads(resolved.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return deepcopy(default)

    with _LOCK:
        _JSON_CACHE[key] = {
            "payload": deepcopy(payload),
            "mtime_ns": int(stat.st_mtime_ns),
            "size": int(stat.st_size),
            "loaded_at": time.time(),
            "dirty": False,
        }
        _METRICS["json_cache_miss_count"] += 1
        _METRICS["json_disk_read_count"] += 1
    return deepcopy(payload)


def queue_json_state(path: Path | str, payload: Any, *, indent: int = 2, sort_keys: bool = False) -> None:
    key, resolved = _path_key(path)
    cloned = deepcopy(payload)
    with _LOCK:
        _PENDING_JSON_WRITES[key] = {
            "path": resolved,
            "payload": cloned,
            "indent": int(indent),
            "sort_keys": bool(sort_keys),
            "queued_at": time.time(),
        }
        _JSON_CACHE[key] = {
            "payload": deepcopy(cloned),
            "mtime_ns": None,
            "size": None,
            "loaded_at": time.time(),
            "dirty": True,
        }


def flush_state_writes(*, paths: list[Path | str] | None = None) -> dict[str, Any]:
    with _LOCK:
        if paths:
            selected = []
            selected_keys = set()
            for raw_path in paths:
                key, _ = _path_key(raw_path)
                pending = _PENDING_JSON_WRITES.get(key)
                if pending is not None and key not in selected_keys:
                    selected.append((key, dict(pending)))
                    selected_keys.add(key)
        else:
            selected = [(key, dict(item)) for key, item in _PENDING_JSON_WRITES.items()]

    flushed: list[str] = []
    failures: list[dict[str, str]] = []
    for key, item in selected:
        path = Path(item["path"])
        payload = deepcopy(item["payload"])
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            serialized = json.dumps(payload, indent=int(item.get("indent", 2)), sort_keys=bool(item.get("sort_keys", False))) + "\n"
            path.write_text(serialized, encoding="utf-8")
            stat = path.stat()
        except Exception as exc:
            failures.append({"path": str(path), "reason": str(exc)})
            continue
        with _LOCK:
            pending = _PENDING_JSON_WRITES.get(key)
            if pending is not None and pending.get("queued_at") == item.get("queued_at"):
                _PENDING_JSON_WRITES.pop(key, None)
            _JSON_CACHE[key] = {
                "payload": deepcopy(payload),
                "mtime_ns": int(stat.st_mtime_ns),
                "size": int(stat.st_size),
                "loaded_at": time.time(),
                "dirty": False,
            }
            _METRICS["json_disk_write_count"] += 1
        flushed.append(str(path))

    with _LOCK:
        if flushed:
            _METRICS["json_flush_count"] += 1
        pending_count = len(_PENDING_JSON_WRITES)
    return {
        "ok": len(failures) == 0,
        "flushed_count": len(flushed),
        "flushed_paths": flushed,
        "failure_count": len(failures),
        "failures": failures,
        "pending_write_count": pending_count,
    }


def clear_state_cache(*, flush: bool = False) -> None:
    if flush:
        flush_state_writes()
    with _LOCK:
        _JSON_CACHE.clear()
        _PENDING_JSON_WRITES.clear()
        for key in list(_METRICS):
            _METRICS[key] = 0


def state_cache_status() -> dict[str, Any]:
    with _LOCK:
        return {
            **dict(_METRICS),
            "cached_entry_count": len(_JSON_CACHE),
            "pending_write_count": len(_PENDING_JSON_WRITES),
            "dirty_path_count": sum(1 for item in _JSON_CACHE.values() if bool(item.get("dirty", False))),
        }
