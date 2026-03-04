"""System capability."""

from __future__ import annotations

from zero_os.types import Result, Task


class SystemCapability:
    name = "system"

    def can_handle(self, task: Task) -> bool:
        keys = ("file", "folder", "system", "os", "run")
        text = task.text.lower()
        return any(k in text for k in keys)

    def run(self, task: Task) -> Result:
        return Result(
            capability=self.name,
            summary=f"System lane accepted task: {task.text}",
        )
