"""User-mode capability for casual/heavy switching."""

from __future__ import annotations

from zero_os.state import get_mode, set_mode
from zero_os.types import Result, Task


class ModeCapability:
    name = "mode"

    def can_handle(self, task: Task) -> bool:
        text = task.text.lower().strip()
        return text.startswith("mode ")

    def run(self, task: Task) -> Result:
        text = task.text.lower().strip()
        if text == "mode show":
            return Result(self.name, f"Current mode: {get_mode(task.cwd)}")
        if text.startswith("mode set "):
            target = text.replace("mode set ", "", 1).strip()
            try:
                mode = set_mode(task.cwd, target)
            except ValueError:
                return Result(self.name, "Supported modes: casual, heavy")
            return Result(self.name, f"Mode switched to: {mode}")
        return Result(
            self.name,
            "Mode commands:\n- mode show\n- mode set casual\n- mode set heavy",
        )

