from __future__ import annotations

import json
import re
from pathlib import Path

from zero_os.browser_session_connector import browser_session_action, browser_session_remember_page
from zero_os.fast_path_cache import cached_compute
from zero_os.net_client import request_text
from zero_os.state_cache import json_state_revision


def _path(cwd: str) -> Path:
    path = Path(cwd).resolve() / ".zero_os" / "connectors" / "browser_dom.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(json.dumps({"pages": {}, "last_selector": "", "last_page": "", "actions": []}, indent=2) + "\n", encoding="utf-8")
    return path


def _build_status(cwd: str) -> dict:
    return json.loads(_path(cwd).read_text(encoding="utf-8", errors="replace"))


def status(cwd: str) -> dict:
    path = _path(cwd)
    data, cache_meta = cached_compute(
        "browser_dom_status",
        str(path),
        lambda: {"browser_dom": json_state_revision(path)},
        lambda: _build_status(cwd),
        ttl_seconds=None,
    )
    data = dict(data)
    data["fast_path_cache"] = {"hit": bool(cache_meta.get("hit", False))}
    return data


def _save(cwd: str, payload: dict) -> None:
    _path(cwd).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _extract_title(html: str) -> str:
    match = re.search(r"<title[^>]*>(.*?)</title>", html, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return ""
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", match.group(1))).strip()


def _extract_text(html: str) -> str:
    text = re.sub(r"<script.*?>.*?</script>", " ", html, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<style.*?>.*?</style>", " ", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _extract_selectors(html: str) -> list[str]:
    selectors = {"body"}
    selectors.update(f"#{match}" for match in re.findall(r'id=["\']([A-Za-z0-9_-]+)["\']', html, flags=re.IGNORECASE))
    selectors.update(f".{match}" for match in re.findall(r'class=["\']([A-Za-z0-9_ -]+)["\']', html, flags=re.IGNORECASE) for match in match.split())
    for tag in ("a", "button", "input", "form", "main", "nav"):
        if re.search(rf"<{tag}\b", html, flags=re.IGNORECASE):
            selectors.add(tag)
    return sorted(selectors)[:120]


def _extract_links(html: str) -> list[dict]:
    out: list[dict] = []
    for href, label in re.findall(r'<a[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', html, flags=re.IGNORECASE | re.DOTALL):
        text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", label)).strip()
        out.append({"href": href.strip(), "label": text})
    return out[:50]


def _extract_forms(html: str) -> list[dict]:
    forms: list[dict] = []
    for form_match in re.finditer(r"<form\b(.*?)>(.*?)</form>", html, flags=re.IGNORECASE | re.DOTALL):
        attrs = form_match.group(1)
        body = form_match.group(2)
        forms.append(
            {
                "action": _extract_attr(attrs, "action"),
                "method": (_extract_attr(attrs, "method") or "get").lower(),
                "input_count": len(re.findall(r"<input\b", body, flags=re.IGNORECASE)),
            }
        )
    return forms[:20]


def _extract_attr(fragment: str, name: str) -> str:
    match = re.search(rf'{name}=["\']([^"\']+)["\']', fragment, flags=re.IGNORECASE)
    return match.group(1).strip() if match else ""


def _page_summary(text: str, title: str, links: list[dict], forms: list[dict]) -> str:
    if not text:
        return title or "empty page"
    preview = text[:220]
    summary_bits = [preview]
    if links:
        summary_bits.append(f"links={len(links)}")
    if forms:
        summary_bits.append(f"forms={len(forms)}")
    return " | ".join(summary_bits)


def inspect_page(cwd: str, url: str) -> dict:
    data = status(cwd)
    response = request_text(url, timeout=8, retries=1)
    response_ok = bool(response.get("ok", False))
    body = str(response.get("body", "")) if response_ok else ""
    title = _extract_title(body)
    text = _extract_text(body)
    links = _extract_links(body)
    forms = _extract_forms(body)
    selectors = _extract_selectors(body) if body else ["body", "a", "input", "button"]
    page = {
        "url": url,
        "status": int(response.get("status", 0) or 0),
        "ok": bool(response.get("ok", False)),
        "title": title,
        "summary": _page_summary(text, title, links, forms),
        "text_preview": text[:500],
        "selectors": selectors,
        "links": links,
        "forms": forms,
        "interactive": bool(links or forms or any(sel in selectors for sel in ("button", "input", "form"))),
    }
    data.setdefault("pages", {})[url] = page
    data["last_page"] = url
    _save(cwd, data)
    if response_ok:
        browser_session_remember_page(cwd, url, page)
        return {"ok": True, "page": page}
    return {
        "ok": False,
        "reason": str(response.get("error", "request_failed")),
        "page": page,
    }


def act(cwd: str, url: str, action: str, selector: str, value: str = "") -> dict:
    data = status(cwd)
    page = dict(data.get("pages", {}).get(url) or {})
    if not page:
        inspected = inspect_page(cwd, url)
        if not inspected.get("ok", False):
            return {"ok": False, "reason": str(inspected.get("reason", "inspect_failed")), "page": dict(inspected.get("page") or {})}
        page = dict(inspected.get("page") or {})
        data = status(cwd)
    elif not bool(page.get("ok", False)):
        return {"ok": False, "reason": "page_not_loaded", "page": page}
    selectors = set(page.get("selectors", []))
    matched_selector = selector if selector in selectors else ""
    if not matched_selector and selector:
        lowered = selector.lower()
        for entry in page.get("links", []):
            label = str(entry.get("label", "")).lower()
            if lowered and lowered in label:
                matched_selector = "a"
                break
    if not matched_selector:
        fallback = {"click": "body", "input": "input", "submit": "form"}.get(action.lower(), "body")
        matched_selector = fallback if fallback in selectors or fallback == "body" else (next(iter(selectors)) if selectors else "body")
    data["last_selector"] = selector
    action_record = {
        "url": url,
        "action": action,
        "selector": matched_selector,
        "requested_selector": selector,
        "value": value,
        "simulated": True,
        "selector_found": matched_selector in selectors or matched_selector == "body",
        "page_title": page.get("title", ""),
    }
    data.setdefault("actions", []).append(action_record)
    data["actions"] = data["actions"][-50:]
    data["last_page"] = url
    _save(cwd, data)
    browser_session_action(cwd, action, matched_selector, value, target=url)
    return {"ok": True, "action": action_record, "page": {"title": page.get("title", ""), "summary": page.get("summary", "")}}
