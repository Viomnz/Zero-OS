"""Agent capability that chains tasks through the same highway."""

from __future__ import annotations

from collections.abc import Callable

from zero_os.types import Result, Task


DispatchFn = Callable[[str, str], Result]


class AgentCapability:
    name = "agent"

    def __init__(self, dispatch_non_agent: DispatchFn) -> None:
        self._dispatch_non_agent = dispatch_non_agent

    def can_handle(self, task: Task) -> bool:
        text = task.text.lower().strip()
        return (
            text.startswith("agent ")
            or text.startswith("agent:")
            or "plan and execute" in text
        )

    def run(self, task: Task) -> Result:
        text = task.text.strip()
        normalized = text.removeprefix("agent:").removeprefix("agent ").strip()
        if normalized.lower().startswith("plan and execute"):
            normalized = normalized[16:].strip(" :")

        steps = [s.strip() for s in normalized.split(" then ") if s.strip()]
        if not steps:
            return Result(self.name, "No executable steps provided.")

        lines: list[str] = []
        for i, step in enumerate(steps, start=1):
            result = self._dispatch_non_agent(step, task.cwd)
            lines.append(f"{i}. [{result.capability}] {step}")
            lines.append(f"   {result.summary}")

        return Result(self.name, "\n".join(lines))

