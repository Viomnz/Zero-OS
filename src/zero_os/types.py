"""Capability interfaces and registry."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass
class Task:
    """A single request entering the Zero OS highway."""

    text: str
    cwd: str = "."
    mode: str = "casual"
    performance_profile: str = "balanced"


@dataclass
class Result:
    """Unified output shape across all capabilities."""

    capability: str
    summary: str


class Capability(Protocol):
    name: str

    def can_handle(self, task: Task) -> bool:
        ...

    def run(self, task: Task) -> Result:
        ...
