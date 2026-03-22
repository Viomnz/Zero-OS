"""Browser automation capability."""

from __future__ import annotations

import re

from zero_os.browser_dom_automation import act as browser_dom_act, inspect_page as browser_dom_inspect
from zero_os.browser_session_connector import browser_session_open, browser_session_status
from zero_os.types import Result, Task


class BrowserCapability:
    name = "browser"

    def can_handle(self, task: Task) -> bool:
        t = task.text.lower().strip()
        return t.startswith("browser ")

    def run(self, task: Task) -> Result:
        raw = task.text.strip()
        lowered = raw.lower()

        open_m = re.match(r"^browser open\s+(.+)$", raw, flags=re.IGNORECASE)
        if open_m:
            url = open_m.group(1).strip()
            if not (url.startswith("http://") or url.startswith("https://")):
                return Result(self.name, "URL must start with http:// or https://")
            opened = browser_session_open(task.cwd, url)
            browser_dom_inspect(task.cwd, opened["url"])
            return Result(self.name, f"browser_opened: {opened['opened']}\nurl: {opened['url']}\nreused_existing: {opened['reused_existing']}")

        tab_m = re.match(r"^browser tabs?\s+open\s+(.+)$", raw, flags=re.IGNORECASE)
        if tab_m:
            urls = [u.strip() for u in tab_m.group(1).split(",") if u.strip()]
            opened = []
            for u in urls[:10]:
                if u.startswith("http://") or u.startswith("https://"):
                    record = browser_session_open(task.cwd, u)
                    browser_dom_inspect(task.cwd, record["url"])
                    opened.append({"url": record["url"], "opened": bool(record["opened"]), "reused_existing": bool(record["reused_existing"])})
            if not opened:
                return Result(self.name, "No valid URLs provided.")
            lines = ["opened tabs:"]
            for item in opened:
                lines.append(f"- {item['url']} (opened={item['opened']}, reused_existing={item['reused_existing']})")
            return Result(self.name, "\n".join(lines))

        inspect_m = re.match(r"^browser inspect\s+(.+)$", raw, flags=re.IGNORECASE)
        if inspect_m:
            page = browser_dom_inspect(task.cwd, inspect_m.group(1).strip())
            result = page.get("page", {})
            return Result(self.name, f"title: {result.get('title', '')}\nsummary: {result.get('summary', '')}")

        action_m = re.match(
            r"^browser act\s+url=(\S+)\s+action=([A-Za-z0-9_-]+)(?:\s+selector=(\S+))?(?:\s+value=(.+))?$",
            raw,
            flags=re.IGNORECASE,
        )
        if action_m:
            result = browser_dom_act(task.cwd, action_m.group(1), action_m.group(2), action_m.group(3) or "", action_m.group(4) or "")
            action = result.get("action", {})
            return Result(self.name, f"action: {action.get('action', '')}\nselector: {action.get('selector', '')}\nselector_found: {action.get('selector_found', False)}")

        if lowered == "browser status":
            session = browser_session_status(task.cwd)
            return Result(self.name, f"tabs: {len(session.get('tabs', []))}\nactive_tab: {session.get('active_tab', '')}\nremembered_pages: {len(session.get('page_memory', {}))}")

        if lowered == "browser help":
            return Result(
                self.name,
                "Browser commands:\n"
                "- browser open <url>\n"
                "- browser tabs open <url1>, <url2>, ...\n",
            )

        return Result(self.name, "Browser commands: browser open <url> | browser tabs open <u1>,<u2> | browser inspect <url> | browser act url=<url> action=<click|input|submit> [selector=<css_or_text>] [value=<text>] | browser status")
