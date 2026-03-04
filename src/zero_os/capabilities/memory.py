"""Memory capability."""

from __future__ import annotations

from zero_os.types import Result, Task


class MemoryCapability:
    name = "memory"

    def can_handle(self, task: Task) -> bool:
        keys = ("remember", "memory", "store", "recall", "note")
        text = task.text.lower()
        return any(k in text for k in keys)

    def run(self, task: Task) -> Result:
        return Result(
            capability=self.name,
            summary=f"Memory lane accepted task: {task.text}",
        )
