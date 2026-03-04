"""Web capability."""

from __future__ import annotations

from zero_os.types import Result, Task


class WebCapability:
    name = "web"

    def can_handle(self, task: Task) -> bool:
        keys = ("web", "search", "browser", "news", "internet")
        text = task.text.lower()
        return any(k in text for k in keys)

    def run(self, task: Task) -> Result:
        return Result(
            capability=self.name,
            summary=f"Web lane accepted task: {task.text}",
        )
