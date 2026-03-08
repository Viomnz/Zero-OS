"""Persistent law storage and export utilities."""

from __future__ import annotations

import hashlib
from pathlib import Path


def _law_path(cwd: str) -> Path:
    return Path(cwd).resolve() / "laws" / "recursion_law.txt"


def law_status(cwd: str) -> str:
    path = _law_path(cwd)
    if not path.exists():
        return f"Law file missing: {path}"
    text = path.read_text(encoding="utf-8", errors="replace")
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return (
        f"Law file: {path}\n"
        f"Characters: {len(text)}\n"
        f"SHA256: {digest}"
    )


def law_export(cwd: str) -> str:
    path = _law_path(cwd)
    if not path.exists():
        return f"Law file missing: {path}"
    return path.read_text(encoding="utf-8", errors="replace")

