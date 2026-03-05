"""Web capability."""

from __future__ import annotations

import re
import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from zero_os.cure_firewall import verify_beacon_net
from zero_os.state import get_net_strict
from zero_os.types import Result, Task


class WebCapability:
    name = "web"

    def can_handle(self, task: Task) -> bool:
        lowered = task.text.lower().strip()
        if lowered.startswith("cure firewall"):
            return False
        if lowered.startswith("znet "):
            return False
        keys = ("web", "search", "news", "internet", "fetch", "http://", "https://")
        text = lowered
        return any(k in text for k in keys)

    def run(self, task: Task) -> Result:
        text = task.text.strip()
        lowered = text.lower()

        if lowered.startswith("search ") or lowered.startswith("web search "):
            query = text.split(" ", 1)[1] if lowered.startswith("search ") else text[11:]
            if query.lower().startswith("multi "):
                return self._search_multi(query[6:].strip(), task.mode, task.performance_profile)
            return self._search(query.strip(), task.mode, task.performance_profile)

        if lowered.startswith("fetch ") or lowered.startswith("web fetch "):
            url = text.split(" ", 1)[1] if lowered.startswith("fetch ") else text[10:]
            if get_net_strict(task.cwd):
                valid, reason = verify_beacon_net(task.cwd, url.strip())
                if not valid:
                    return Result(
                        self.name,
                        (
                            "Blocked by net strict mode: URL is unverified.\n"
                            f"verify_reason: {reason}\n"
                            "Run: cure firewall net run <url> pressure <0-100>"
                        ),
                    )
            return self._fetch(url.strip(), task.mode, task.performance_profile)

        return Result(
            self.name,
            "Actionable web commands:\n- search <query>\n- search multi <query>\n- fetch <url>",
        )

    def _search_multi(self, query: str, mode: str, profile: str) -> Result:
        if not query:
            return Result(self.name, "Search query is empty.")
        if mode == "heavy":
            limit = {"low": 6, "balanced": 10, "high": 14}.get(profile, 10)
        else:
            limit = {"low": 3, "balanced": 5, "high": 7}.get(profile, 5)

        results = []
        # Source 1: DuckDuckGo HTML results.
        ddg = self._search_duckduckgo(query, max_results=limit)
        for r in ddg:
            r["source"] = "duckduckgo"
            results.append(r)

        # Source 2: Wikipedia OpenSearch API.
        wiki = self._search_wikipedia(query, max_results=max(2, limit // 2))
        for r in wiki:
            r["source"] = "wikipedia"
            results.append(r)

        # Rank: simple source diversity + title length heuristic.
        dedup = {}
        for r in results:
            key = r["url"]
            if key not in dedup:
                dedup[key] = r
        ranked = sorted(
            dedup.values(),
            key=lambda x: (0 if x["source"] == "wikipedia" else 1, len(x["title"])),
        )[:limit]

        if not ranked:
            return Result(self.name, f'No results for "{query}".')
        lines = [f'Multi-source results for "{query}" (with citations):']
        for i, r in enumerate(ranked, start=1):
            lines.append(f"{i}. {r['title']} [{r['source']}]")
            lines.append(f"   citation: {r['url']}")
        return Result(self.name, "\n".join(lines))

    def _search(self, query: str, mode: str, profile: str) -> Result:
        if not query:
            return Result(self.name, "Search query is empty.")
        if mode == "heavy":
            limit = {"low": 5, "balanced": 8, "high": 12}.get(profile, 8)
        else:
            limit = {"low": 2, "balanced": 3, "high": 5}.get(profile, 3)
        matches = self._search_duckduckgo(query, max_results=limit)
        if not matches:
            return Result(self.name, f'No results for "{query}".')

        lines = [f'Results for "{query}":']
        for m in matches[:limit]:
            lines.append(f"- {m['title']} ({m['url']})")
        return Result(self.name, "\n".join(lines))

    def _search_duckduckgo(self, query: str, max_results: int) -> list[dict[str, str]]:
        params = urlencode({"q": query})
        url = f"https://duckduckgo.com/html/?{params}"
        request = Request(url, headers={"User-Agent": "Zero-OS/0.1"})
        with urlopen(request, timeout=10) as response:
            html = response.read().decode("utf-8", errors="replace")
        matches = re.findall(
            r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
            html,
            flags=re.IGNORECASE | re.DOTALL,
        )
        out = []
        for link, raw_title in matches[:max_results]:
            title = re.sub(r"<[^>]+>", "", raw_title).strip()
            out.append({"title": title or link, "url": link})
        return out

    def _search_wikipedia(self, query: str, max_results: int) -> list[dict[str, str]]:
        api = "https://en.wikipedia.org/w/api.php?" + urlencode(
            {"action": "opensearch", "search": query, "limit": max_results, "namespace": 0, "format": "json"}
        )
        req = Request(api, headers={"User-Agent": "Zero-OS/0.1"})
        with urlopen(req, timeout=10) as response:
            body = response.read().decode("utf-8", errors="replace")
        data = json.loads(body)
        titles = data[1] if isinstance(data, list) and len(data) > 1 else []
        urls = data[3] if isinstance(data, list) and len(data) > 3 else []
        out = []
        for t, u in zip(titles, urls):
            out.append({"title": str(t), "url": str(u)})
        return out

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
