from __future__ import annotations

from contextlib import contextmanager
import json
import os
import threading
import time
import webbrowser
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from zero_os.fast_path_cache import cached_compute
from zero_os.state_cache import json_state_revision


def _session_path(cwd: str) -> Path:
    path = Path(cwd).resolve() / ".zero_os" / "connectors" / "browser_session.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(json.dumps(_default_session(), indent=2) + "\n", encoding="utf-8")
    return path


def _default_session() -> dict:
    return {
        "tabs": [],
        "last_opened": "",
        "active_tab": "",
        "history": [],
        "actions": [],
        "page_memory": {},
    }


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _lock_path(cwd: str) -> Path:
    return _session_path(cwd).with_name("browser_session.lock")


@contextmanager
def _session_lock(cwd: str, *, timeout_seconds: float = 2.0, stale_after_seconds: float = 10.0):
    lock_path = _lock_path(cwd)
    deadline = time.monotonic() + timeout_seconds
    owner = f"{os.getpid()}:{threading.get_ident()}:{_utc_now()}"
    while True:
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            try:
                os.write(fd, owner.encode("utf-8", errors="replace"))
            finally:
                os.close(fd)
            break
        except FileExistsError:
            try:
                age_seconds = time.time() - lock_path.stat().st_mtime
            except FileNotFoundError:
                continue
            if age_seconds >= stale_after_seconds:
                try:
                    lock_path.unlink()
                except FileNotFoundError:
                    continue
                continue
            if time.monotonic() >= deadline:
                raise TimeoutError(f"browser_session_lock_timeout:{lock_path}")
            time.sleep(0.01)
    try:
        yield
    finally:
        try:
            lock_path.unlink()
        except FileNotFoundError:
            pass


def _parse_utc(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None


def _normalize_url(url: str) -> str:
    raw = str(url or "").strip()
    if not raw:
        return ""
    parts = urlsplit(raw)
    scheme = parts.scheme.lower()
    netloc = parts.netloc.lower()
    path = parts.path or ""
    if path == "/":
        path = ""
    normalized = urlunsplit((scheme, netloc, path, parts.query, ""))
    return normalized.rstrip("/")


def _load_session(cwd: str) -> dict:
    path = _session_path(cwd)
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        data = _default_session()
    if not isinstance(data, dict):
        data = _default_session()
    for key, value in _default_session().items():
        data.setdefault(key, value if not isinstance(value, dict) else dict(value))
    return data


def _save_session(cwd: str, data: dict) -> dict:
    _session_path(cwd).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return data


def _compact_tabs(data: dict) -> dict:
    seen_urls: set[str] = set()
    compacted: list[dict] = []
    for tab in reversed(list(data.get("tabs", []))):
        normalized = _normalize_url(tab.get("url", ""))
        if not normalized:
            continue
        if normalized in seen_urls:
            continue
        seen_urls.add(normalized)
        launch_attempted = bool(tab.get("launch_attempted", False) or tab.get("opened", False))
        compacted.append(
            {
                "url": normalized,
                "opened": bool(tab.get("opened", False) or launch_attempted),
                "launch_attempted": launch_attempted,
                "launch_result": bool(tab.get("launch_result", tab.get("opened", False))),
                "opened_utc": str(tab.get("opened_utc", "")),
            }
        )
    compacted.reverse()
    data["tabs"] = compacted[-20:]
    data["last_opened"] = _normalize_url(data.get("last_opened", "")) or (data["tabs"][-1]["url"] if data["tabs"] else "")
    data["active_tab"] = _normalize_url(data.get("active_tab", "")) or data["last_opened"]

    history: list[dict] = []
    for event in list(data.get("history", [])):
        normalized = _normalize_url(event.get("url", ""))
        if not normalized:
            continue
        history.append(
            {
                "url": normalized,
                "opened": bool(event.get("opened", False)),
                "reused_existing": bool(event.get("reused_existing", False)),
                "opened_utc": str(event.get("opened_utc", "")),
            }
        )
    data["history"] = history[-100:]
    return data


def _recent_duplicate_open(data: dict, normalized: str, cooldown_seconds: int = 5) -> bool:
    if not normalized:
        return False
    for event in reversed(list(data.get("history", []))):
        if _normalize_url(event.get("url", "")) != normalized:
            continue
        opened_at = _parse_utc(str(event.get("opened_utc", "")))
        if opened_at is None:
            return bool(event.get("opened", False))
        age = (datetime.now(timezone.utc) - opened_at).total_seconds()
        return bool(event.get("opened", False)) and age <= cooldown_seconds
    return False


def _build_browser_session_status(cwd: str) -> dict:
    loaded = _load_session(cwd)
    compacted = _compact_tabs(dict(loaded))
    if compacted != loaded:
        _save_session(cwd, compacted)
    return compacted


def browser_session_status(cwd: str) -> dict:
    path = _session_path(cwd)
    status, cache_meta = cached_compute(
        "browser_session_status",
        str(path),
        lambda: {"session": json_state_revision(path)},
        lambda: _build_browser_session_status(cwd),
        ttl_seconds=None,
    )
    status = dict(status)
    status["fast_path_cache"] = {"hit": bool(cache_meta.get("hit", False))}
    return status


def browser_session_open(cwd: str, url: str) -> dict:
    normalized = _normalize_url(url)
    with _session_lock(cwd):
        loaded = _load_session(cwd)
        data = _compact_tabs(dict(loaded))
        if data != loaded:
            _save_session(cwd, data)

        existing_tab = next((tab for tab in data.get("tabs", []) if tab.get("url") == normalized), None)
        recent_duplicate = _recent_duplicate_open(data, normalized)
        already_active = normalized and normalized in {
            _normalize_url(data.get("active_tab", "")),
            _normalize_url(data.get("last_opened", "")),
        }

        reused_existing = existing_tab is not None or recent_duplicate or already_active
        launch_attempted = bool(existing_tab.get("launch_attempted", False)) if existing_tab else False
        launch_result = bool(existing_tab.get("launch_result", False)) if existing_tab else False
        if existing_tab:
            opened = bool(existing_tab.get("opened", False) or launch_attempted)
        elif reused_existing:
            launch_attempted = True
            opened = True
        else:
            launch_result = bool(webbrowser.open(normalized, new=2))
            launch_attempted = True
            opened = True
        opened_utc = _utc_now()

        if not existing_tab:
            data.setdefault("tabs", []).append(
                {
                    "url": normalized,
                    "opened": opened,
                    "launch_attempted": launch_attempted,
                    "launch_result": launch_result,
                    "opened_utc": opened_utc,
                }
            )
            data["tabs"] = data["tabs"][-20:]
        else:
            existing_tab["opened"] = opened
            existing_tab["launch_attempted"] = bool(existing_tab.get("launch_attempted", False) or launch_attempted)
            existing_tab["launch_result"] = bool(existing_tab.get("launch_result", False) or launch_result)
        data["last_opened"] = normalized
        data["active_tab"] = normalized
        data.setdefault("history", []).append(
            {
                "url": normalized,
                "opened": opened,
                "reused_existing": reused_existing,
                "launch_attempted": launch_attempted,
                "launch_result": launch_result,
                "opened_utc": opened_utc,
            }
        )
        data["history"] = data["history"][-100:]
        _save_session(cwd, _compact_tabs(data))
    return {
        "ok": True,
        "url": normalized,
        "opened": opened,
        "reused_existing": reused_existing,
        "launch_attempted": launch_attempted,
        "launch_result": launch_result,
        "session": data,
    }


def browser_session_remember_page(cwd: str, url: str, page: dict) -> dict:
    data = browser_session_status(cwd)
    normalized = _normalize_url(url)
    memory = dict(data.get("page_memory", {}))
    memory[normalized] = {
        "url": normalized,
        "title": str(page.get("title", "")),
        "summary": str(page.get("summary", "")),
        "selector_count": int(len(page.get("selectors", []))),
        "link_count": int(len(page.get("links", []))),
        "interactive": bool(page.get("interactive", False)),
    }
    data["page_memory"] = memory
    _save_session(cwd, data)
    return memory[normalized]


def browser_session_action(cwd: str, action: str, selector: str = "", value: str = "", target: str = "") -> dict:
    data = browser_session_status(cwd)
    normalized_target = _normalize_url(target) or _normalize_url(data.get("active_tab", "")) or _normalize_url(data.get("last_opened", ""))
    event = {
        "action": str(action).strip().lower(),
        "selector": str(selector).strip(),
        "value": value,
        "target": normalized_target,
        "simulated": True,
    }
    data.setdefault("actions", []).append(event)
    data["actions"] = list(data.get("actions", []))[-100:]
    if normalized_target:
        data["active_tab"] = normalized_target
        data["last_opened"] = normalized_target
    _save_session(cwd, data)
    return {"ok": True, "action": event, "session": data}
