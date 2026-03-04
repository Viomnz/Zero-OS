"""System capability."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import getpass

from zero_os.types import Result, Task


class SystemCapability:
    name = "system"

    def can_handle(self, task: Task) -> bool:
        keys = (
            "system",
            "list files",
            "show files",
            "current directory",
            "current dir",
            "pwd",
            "whoami",
            "date",
            "time",
        )
        text = task.text.lower()
        return any(k in text for k in keys)

    def run(self, task: Task) -> Result:
        text = task.text.lower()
        cwd = Path(task.cwd).resolve()

        if "list files" in text or "show files" in text:
            names = sorted(p.name for p in cwd.iterdir())
            if not names:
                return Result(self.name, f"{cwd}\n(empty)")
            return Result(self.name, f"{cwd}\n" + "\n".join(names))

        if "current dir" in text or "current directory" in text or "pwd" in text:
            return Result(self.name, str(cwd))

        if "whoami" in text or "user" in text:
            return Result(self.name, getpass.getuser())

        if "time" in text or "date" in text:
            return Result(self.name, datetime.now().isoformat(timespec="seconds"))

        return Result(
            self.name,
            "Actionable system commands:\n"
            "- list files\n"
            "- current directory\n"
            "- whoami\n"
            "- date/time",
        )
