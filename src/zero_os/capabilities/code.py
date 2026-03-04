"""Code capability."""

from __future__ import annotations

from zero_os.types import Result, Task


class CodeCapability:
    name = "code"

    def can_handle(self, task: Task) -> bool:
        keys = ("code", "build", "debug", "fix", "refactor")
        text = task.text.lower()
        return any(k in text for k in keys)

    def run(self, task: Task) -> Result:
        return Result(
            capability=self.name,
            summary=f"Code lane accepted task: {task.text}",
        )
