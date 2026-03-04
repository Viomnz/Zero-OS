"""Code capability."""

from __future__ import annotations

import re
import shutil
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
            "add to",
            "read file",
            "write ",
            "new ",
            "show ",
            "delete ",
            "remove ",
            "rename ",
            "move ",
            "copy ",
            "mkdir ",
        )
        return any(k in text for k in keys)

    def run(self, task: Task) -> Result:
        text = task.text.strip()
        lowered = text.lower()
        base = Path(task.cwd)
        commands = [c.strip() for c in re.split(r"\s+then\s+|;", text, flags=re.IGNORECASE) if c.strip()]

        if len(commands) > 1:
            lines: list[str] = []
            for i, cmd in enumerate(commands, start=1):
                lines.append(f"{i}. {self._execute_single(cmd, base)}")
            return Result(self.name, "\n".join(lines))
        return Result(self.name, self._execute_single(text, base))

    def _execute_single(self, text: str, base: Path) -> str:
        lowered = text.lower().strip()

        create = re.match(
            r"^(?:create file|new file|write)\s+(.+?)\s+(?:with|:)\s+(.+)$",
            text,
            flags=re.IGNORECASE,
        )
        if create:
            rel_path = create.group(1).strip().strip("\"'")
            content = create.group(2)
            file_path = (base / rel_path).resolve()
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content + "\n", encoding="utf-8")
            return f"Created file: {file_path}"

        append = re.match(
            r"^(?:append to|add to)\s+(.+?):\s*(.+)$", text, flags=re.IGNORECASE
        )
        if append:
            rel_path = append.group(1).strip().strip("\"'")
            content = append.group(2)
            file_path = (base / rel_path).resolve()
            file_path.parent.mkdir(parents=True, exist_ok=True)
            with file_path.open("a", encoding="utf-8") as handle:
                handle.write(content + "\n")
            return f"Appended to file: {file_path}"

        read = re.match(
            r"^(?:read file|show file|open file|show)\s+(.+)$", text, flags=re.IGNORECASE
        )
        if read:
            rel_path = read.group(1).strip().strip("\"'")
            file_path = (base / rel_path).resolve()
            if not file_path.exists():
                return f"File not found: {file_path}"
            data = file_path.read_text(encoding="utf-8", errors="replace")
            preview = data[:500] if data else "(empty file)"
            return f"{file_path}\n{preview}"

        mkdir = re.match(r"^(?:mkdir|create folder|new folder)\s+(.+)$", text, flags=re.IGNORECASE)
        if mkdir:
            rel_path = mkdir.group(1).strip().strip("\"'")
            dir_path = (base / rel_path).resolve()
            dir_path.mkdir(parents=True, exist_ok=True)
            return f"Created folder: {dir_path}"

        rename = re.match(r"^(?:rename|move)\s+(.+?)\s+to\s+(.+)$", text, flags=re.IGNORECASE)
        if rename:
            src = (base / rename.group(1).strip().strip("\"'")).resolve()
            dst = (base / rename.group(2).strip().strip("\"'")).resolve()
            if not src.exists():
                return f"Source not found: {src}"
            dst.parent.mkdir(parents=True, exist_ok=True)
            src.rename(dst)
            return f"Moved: {src} -> {dst}"

        copy = re.match(r"^copy\s+(.+?)\s+to\s+(.+)$", text, flags=re.IGNORECASE)
        if copy:
            src = (base / copy.group(1).strip().strip("\"'")).resolve()
            dst = (base / copy.group(2).strip().strip("\"'")).resolve()
            if not src.exists():
                return f"Source not found: {src}"
            dst.parent.mkdir(parents=True, exist_ok=True)
            if src.is_dir():
                shutil.copytree(src, dst, dirs_exist_ok=True)
            else:
                shutil.copy2(src, dst)
            return f"Copied: {src} -> {dst}"

        delete = re.match(r"^(?:delete|remove)\s+(.+)$", text, flags=re.IGNORECASE)
        if delete:
            target = (base / delete.group(1).strip().strip("\"'")).resolve()
            if not target.exists():
                return f"Target not found: {target}"
            if target.is_dir():
                shutil.rmtree(target)
            else:
                target.unlink()
            return f"Deleted: {target}"

        if "build" in lowered or "code" in lowered or "refactor" in lowered:
            return (
                "Actionable code commands:\n"
                "- create file <path> with <content>\n"
                "- append to <path>: <content>\n"
                "- read/show file <path>\n"
                "- mkdir <path>\n"
                "- rename <src> to <dst>\n"
                "- copy <src> to <dst>\n"
                "- delete <path>\n"
                "- chain commands with `then` or `;`",
            )

        return f"Code lane received: {text}"
