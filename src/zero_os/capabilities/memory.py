"""Memory capability."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from zero_os.types import Result, Task


class MemoryCapability:
    name = "memory"

    def can_handle(self, task: Task) -> bool:
        text = task.text.lower()
        if text.startswith(("remember ", "store ", "recall", "memory clear")):
            return True
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
        text = task.text.strip()
        lowered = text.lower()
        store_path = Path(task.cwd).resolve() / ".zero_os" / "memory.json"
        store_path.parent.mkdir(parents=True, exist_ok=True)
        records = self._load_records(store_path)

        if lowered.startswith("remember "):
            return self._remember(records, store_path, text[9:].strip())
        if lowered.startswith("store "):
            return self._remember(records, store_path, text[6:].strip())
        if lowered == "recall":
            return self._recall(records, "")
        if lowered.startswith("recall "):
            return self._recall(records, text[7:].strip())
        if lowered == "memory clear":
            store_path.write_text("[]\n", encoding="utf-8")
            return Result(self.name, f"Cleared memory store: {store_path}")

        return Result(
            self.name,
            "Actionable memory commands:\n"
            "- remember <text>\n"
            "- store <text>\n"
            "- recall [filter]\n"
            "- memory clear",
        )

    def _load_records(self, store_path: Path) -> list[dict[str, str]]:
        if not store_path.exists():
            return []
        raw = store_path.read_text(encoding="utf-8", errors="replace").strip()
        if not raw:
            return []
        try:
            data = json.loads(raw)
            if isinstance(data, list):
                return [r for r in data if isinstance(r, dict)]
        except json.JSONDecodeError:
            return []
        return []

    def _remember(
        self,
        records: list[dict[str, str]],
        store_path: Path,
        value: str,
    ) -> Result:
        if not value:
            return Result(self.name, "Nothing to store.")
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "value": value,
        }
        records.append(record)
        store_path.write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")
        return Result(self.name, f"Stored memory item #{len(records)}")

    def _recall(self, records: list[dict[str, str]], needle: str) -> Result:
        if not records:
            return Result(self.name, "Memory is empty.")
        filtered = records
        if needle:
            lowered = needle.lower()
            filtered = [r for r in records if lowered in r.get("value", "").lower()]
        if not filtered:
            return Result(self.name, f'No memory matches "{needle}".')
        recent = filtered[-10:]
        lines = ["Memory recall:"]
        for i, item in enumerate(recent, start=1):
            lines.append(f'{i}. {item.get("timestamp", "")} | {item.get("value", "")}')
        return Result(self.name, "\n".join(lines))
