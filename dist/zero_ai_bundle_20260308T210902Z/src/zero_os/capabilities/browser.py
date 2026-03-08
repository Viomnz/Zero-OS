"""Browser automation capability."""

from __future__ import annotations

import re
import webbrowser

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
            opened = webbrowser.open(url, new=2)
            return Result(self.name, f"browser_opened: {opened}\nurl: {url}")

        tab_m = re.match(r"^browser tabs?\s+open\s+(.+)$", raw, flags=re.IGNORECASE)
        if tab_m:
            urls = [u.strip() for u in tab_m.group(1).split(",") if u.strip()]
            opened = []
            for u in urls[:10]:
                if u.startswith("http://") or u.startswith("https://"):
                    opened.append({"url": u, "opened": bool(webbrowser.open(u, new=2))})
            if not opened:
                return Result(self.name, "No valid URLs provided.")
            lines = ["opened tabs:"]
            for item in opened:
                lines.append(f"- {item['url']} (opened={item['opened']})")
            return Result(self.name, "\n".join(lines))

        if lowered == "browser help":
            return Result(
                self.name,
                "Browser commands:\n"
                "- browser open <url>\n"
                "- browser tabs open <url1>, <url2>, ...\n",
            )

        return Result(self.name, "Browser commands: browser open <url> | browser tabs open <u1>,<u2>")
