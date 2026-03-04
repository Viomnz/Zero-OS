"""Single highway router for Zero OS."""

from __future__ import annotations

from zero_os.capabilities.code import CodeCapability
from zero_os.capabilities.memory import MemoryCapability
from zero_os.capabilities.system import SystemCapability
from zero_os.capabilities.web import WebCapability
from zero_os.types import Capability, Result, Task


class Highway:
    """One path in, one routing decision, one unified result."""

    def __init__(self) -> None:
        self.capabilities: list[Capability] = [
            CodeCapability(),
            WebCapability(),
            SystemCapability(),
            MemoryCapability(),
        ]

    def dispatch(self, text: str, cwd: str = ".") -> Result:
        task = Task(text=text, cwd=cwd)
        for capability in self.capabilities:
            if capability.can_handle(task):
                return capability.run(task)

        return Result(
            capability="fallback",
            summary=(
                "No lane matched this task yet. Add a capability or expand keywords."
            ),
        )
