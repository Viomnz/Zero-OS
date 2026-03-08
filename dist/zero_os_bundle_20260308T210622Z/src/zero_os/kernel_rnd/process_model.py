from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Process:
    pid: int
    name: str
    state: str = "ready"


class ProcessTable:
    def __init__(self) -> None:
        self._next_pid = 1
        self._procs: dict[int, Process] = {}

    def spawn(self, name: str) -> Process:
        p = Process(pid=self._next_pid, name=name, state="running")
        self._procs[p.pid] = p
        self._next_pid += 1
        return p

    def exit(self, pid: int) -> bool:
        proc = self._procs.get(int(pid))
        if not proc:
            return False
        proc.state = "exited"
        return True

    def list(self) -> list[dict]:
        return [
            {"pid": p.pid, "name": p.name, "state": p.state}
            for p in sorted(self._procs.values(), key=lambda x: x.pid)
        ]
