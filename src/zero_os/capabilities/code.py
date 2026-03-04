"""Code capability."""

from __future__ import annotations

import re
from pathlib import Path

from zero_os.types import Result, Task


class CodeCapability:
    name = "code"

    def can_handle(self, task: Task) -> bool:
        text = task.text.lower().strip()
        keys = (
            "code",
            "build",
            "debug",
            "fix",
            "refactor",
            "create file",
            "append to",
            "read file",
        )
        return any(k in text for k in keys)

    def run(self, task: Task) -> Result:
        text = task.text.strip()
        lowered = text.lower()
        base = Path(task.cwd)

        create = re.match(
            r"^create file\s+(.+?)\s+with\s+(.+)$", text, flags=re.IGNORECASE
        )
        if create:
            rel_path = create.group(1).strip().strip("\"'")
            content = create.group(2)
            file_path = (base / rel_path).resolve()
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content + "\n", encoding="utf-8")
            return Result(self.name, f"Created file: {file_path}")

        append = re.match(r"^append to\s+(.+?):\s*(.+)$", text, flags=re.IGNORECASE)
        if append:
            rel_path = append.group(1).strip().strip("\"'")
            content = append.group(2)
            file_path = (base / rel_path).resolve()
            file_path.parent.mkdir(parents=True, exist_ok=True)
            with file_path.open("a", encoding="utf-8") as handle:
                handle.write(content + "\n")
            return Result(self.name, f"Appended to file: {file_path}")

        read = re.match(r"^read file\s+(.+)$", text, flags=re.IGNORECASE)
        if read:
            rel_path = read.group(1).strip().strip("\"'")
            file_path = (base / rel_path).resolve()
            if not file_path.exists():
                return Result(self.name, f"File not found: {file_path}")
            data = file_path.read_text(encoding="utf-8", errors="replace")
            preview = data[:500] if data else "(empty file)"
            return Result(self.name, f"{file_path}\n{preview}")

        if "build" in lowered or "code" in lowered or "refactor" in lowered:
            return Result(
                self.name,
                "Actionable code commands:\n"
                "- create file <path> with <content>\n"
                "- append to <path>: <content>\n"
                "- read file <path>",
            )

        return Result(self.name, f"Code lane received: {task.text}")
