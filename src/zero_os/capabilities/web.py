"""Web capability."""

from __future__ import annotations

import json
import re
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from zero_os.types import Result, Task


class WebCapability:
    name = "web"

    def can_handle(self, task: Task) -> bool:
        keys = ("web", "search", "browser", "news", "internet", "fetch", "http://", "https://")
        text = task.text.lower()
        return any(k in text for k in keys)

    def run(self, task: Task) -> Result:
        text = task.text.strip()
        lowered = text.lower()

        if lowered.startswith("search ") or lowered.startswith("web search "):
            query = text.split(" ", 1)[1] if lowered.startswith("search ") else text[11:]
            return self._search(query.strip(), task.mode, task.performance_profile)

        if lowered.startswith("fetch ") or lowered.startswith("web fetch "):
            url = text.split(" ", 1)[1] if lowered.startswith("fetch ") else text[10:]
            return self._fetch(url.strip(), task.mode, task.performance_profile)

        return Result(
            self.name,
            "Actionable web commands:\n- search <query>\n- fetch <url>",
        )

    def _search(self, query: str, mode: str, profile: str) -> Result:
        if not query:
            return Result(self.name, "Search query is empty.")
        if mode == "heavy":
            limit = {"low": 5, "balanced": 8, "high": 12}.get(profile, 8)
        else:
            limit = {"low": 2, "balanced": 3, "high": 5}.get(profile, 3)
        params = urlencode(
            {
                "action": "opensearch",
                "search": query,
                "limit": limit,
                "namespace": 0,
                "format": "json",
            }
        )
        url = f"https://en.wikipedia.org/w/api.php?{params}"
        request = Request(url, headers={"User-Agent": "Zero-OS/0.1"})
        with urlopen(request, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8", errors="replace"))

        titles = payload[1]
        descriptions = payload[2]
        links = payload[3]
        if not titles:
            return Result(self.name, f'No results for "{query}".')

        lines = [f'Results for "{query}":']
        for title, description, link in zip(titles, descriptions, links):
            desc = description or "No description"
            lines.append(f"- {title}: {desc} ({link})")
        return Result(self.name, "\n".join(lines))

    def _fetch(self, url: str, mode: str, profile: str) -> Result:
        if not (url.startswith("http://") or url.startswith("https://")):
            return Result(self.name, "URL must start with http:// or https://")

        request = Request(url, headers={"User-Agent": "Zero-OS/0.1"})
        with urlopen(request, timeout=10) as response:
            content_type = response.headers.get("Content-Type", "")
            body = response.read().decode("utf-8", errors="replace")

        text = body
        if "text/html" in content_type:
            text = re.sub(r"<script.*?>.*?</script>", " ", text, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r"<style.*?>.*?</style>", " ", text, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r"<[^>]+>", " ", text)
            text = re.sub(r"\s+", " ", text).strip()
        if mode == "heavy":
            preview_len = {"low": 1200, "balanced": 2400, "high": 4000}.get(
                profile, 2400
            )
        else:
            preview_len = {"low": 400, "balanced": 700, "high": 1000}.get(profile, 700)
        preview = text[:preview_len] if text else "(empty response)"
        return Result(self.name, f"{url}\n{preview}")
