"""API connector capability (REST)."""

from __future__ import annotations

import json
import re
from urllib.request import Request, urlopen

from zero_os.types import Result, Task


class ApiCapability:
    name = "api"

    def can_handle(self, task: Task) -> bool:
        t = task.text.lower().strip()
        return t.startswith("api get ") or t.startswith("api post ") or t == "api help"

    def run(self, task: Task) -> Result:
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
        req = Request(url, headers={"User-Agent": "Zero-OS/0.1", "Accept": "application/json, text/plain, */*"})
        with urlopen(req, timeout=12) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            ctype = resp.headers.get("Content-Type", "")
            status = getattr(resp, "status", 200)
        text = body[:1600] if body else "(empty response)"
        return Result(self.name, f"status: {status}\ncontent_type: {ctype}\nurl: {url}\n{text}")

    def _post_json(self, url: str, obj: str) -> Result:
        if not (url.startswith("http://") or url.startswith("https://")):
            return Result(self.name, "URL must start with http:// or https://")
        try:
            payload = json.loads(obj)
        except json.JSONDecodeError:
            return Result(self.name, "Invalid JSON payload.")
        raw = json.dumps(payload).encode("utf-8")
        req = Request(
            url,
            data=raw,
            method="POST",
            headers={
                "User-Agent": "Zero-OS/0.1",
                "Content-Type": "application/json",
                "Accept": "application/json, text/plain, */*",
            },
        )
        with urlopen(req, timeout=12) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            ctype = resp.headers.get("Content-Type", "")
            status = getattr(resp, "status", 200)
        text = body[:1600] if body else "(empty response)"
        return Result(self.name, f"status: {status}\ncontent_type: {ctype}\nurl: {url}\n{text}")
