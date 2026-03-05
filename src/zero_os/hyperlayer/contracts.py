from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ZeroApiResult:
    ok: bool
    op: str
    backend: str
    detail: dict


class ZeroApi:
    def backend_name(self) -> str:
        raise NotImplementedError

    def get_system_info(self) -> ZeroApiResult:
        raise NotImplementedError

    def list_processes(self, limit: int = 20) -> ZeroApiResult:
        raise NotImplementedError

    def run_shell(self, command: str) -> ZeroApiResult:
        raise NotImplementedError
