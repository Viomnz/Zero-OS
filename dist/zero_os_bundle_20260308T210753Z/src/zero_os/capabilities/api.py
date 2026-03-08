"""API connector capability (REST)."""

from __future__ import annotations

import json
import re

from zero_os.net_client import request_text
from zero_os.rate_limit import check_and_record
from zero_os.types import Result, Task


class ApiCapability:
    name = "api"

    def can_handle(self, task: Task) -> bool:
        t = task.text.lower().strip()
        return t.startswith("api get ") or t.startswith("api post ") or t == "api help"

    def run(self, task: Task) -> Result:
        allowed, state = check_and_record(task.cwd, "api", limit=30, window_seconds=60)
        if not allowed:
            return Result(
                self.name,
                (
                    "Rate limit exceeded for api lane.\n"
                    f"retry_after_seconds: {state['retry_after_seconds']}\n"
                    f"limit: {state['limit']}/{state['window_seconds']}s"
                ),
            )
        raw = task.text.strip()
        if raw.lower() == "api help":
            return Result(self.name, "API commands:\n- api get <url>\n- api post <url> json <object>")

        get_m = re.match(r"^api get\s+(.+)$", raw, flags=re.IGNORECASE)
        if get_m:
            return self._get(get_m.group(1).strip())

        post_m = re.match(r"^api post\s+(\S+)\s+json\s+(.+)$", raw, flags=re.IGNORECASE)
        if post_m:
            return self._post_json(post_m.group(1).strip(), post_m.group(2).strip())

        return Result(self.name, "API commands:\n- api get <url>\n- api post <url> json <object>")

    def _get(self, url: str) -> Result:
        if not (url.startswith("http://") or url.startswith("https://")):
            return Result(self.name, "URL must start with http:// or https://")
        res = request_text(
            url,
            method="GET",
            headers={"Accept": "application/json, text/plain, */*"},
            timeout=12,
            retries=2,
        )
        if not res.get("ok", False):
            return Result(
                self.name,
                (
                    f"status: {res.get('status', 0)}\n"
                    f"url: {url}\n"
                    f"attempts: {res.get('attempts', 1)}\n"
                    f"error: {res.get('error', 'request failed')}"
                ),
            )
        text = str(res.get("body", ""))[:1600] or "(empty response)"
        return Result(
            self.name,
            f"status: {res.get('status', 200)}\ncontent_type: {res.get('content_type', '')}\nurl: {url}\n{text}",
        )

    def _post_json(self, url: str, obj: str) -> Result:
        if not (url.startswith("http://") or url.startswith("https://")):
            return Result(self.name, "URL must start with http:// or https://")
        try:
            payload = json.loads(obj)
        except json.JSONDecodeError:
            return Result(self.name, "Invalid JSON payload.")
        raw = json.dumps(payload).encode("utf-8")
        res = request_text(
            url,
            method="POST",
            data=raw,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json, text/plain, */*",
            },
            timeout=12,
            retries=2,
        )
        if not res.get("ok", False):
            return Result(
                self.name,
                (
                    f"status: {res.get('status', 0)}\n"
                    f"url: {url}\n"
                    f"attempts: {res.get('attempts', 1)}\n"
                    f"error: {res.get('error', 'request failed')}"
                ),
            )
        text = str(res.get("body", ""))[:1600] or "(empty response)"
        return Result(
            self.name,
            f"status: {res.get('status', 200)}\ncontent_type: {res.get('content_type', '')}\nurl: {url}\n{text}",
        )
