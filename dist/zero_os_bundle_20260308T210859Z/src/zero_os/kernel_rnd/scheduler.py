from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Task:
    tid: int
    name: str
    priority: int = 0
    timeslice_ms: int = 10


class RoundRobinScheduler:
    def __init__(self) -> None:
        self.queue: list[Task] = []
        self.cursor: int = 0

    def add(self, task: Task) -> None:
        self.queue.append(task)

    def next_task(self) -> Task | None:
        if not self.queue:
            return None
        t = self.queue[self.cursor % len(self.queue)]
        self.cursor = (self.cursor + 1) % len(self.queue)
        return t
