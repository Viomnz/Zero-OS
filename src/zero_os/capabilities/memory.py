"""Memory capability."""

from __future__ import annotations

import re

from zero_os.types import Result, Task


class MemoryCapability:
    name = "memory"

    def can_handle(self, task: Task) -> bool:
        text = task.text.lower()
        return any(
            re.search(pattern, text) is not None
            for pattern in (
                r"\bremember\b",
                r"\bmemory\b",
                r"\bstore\b",
                r"\brecall\b",
                r"\bnote\b",
            )
        )

    def run(self, task: Task) -> Result:
        return Result(
            capability=self.name,
            summary=f"Memory lane accepted task: {task.text}",
        )
