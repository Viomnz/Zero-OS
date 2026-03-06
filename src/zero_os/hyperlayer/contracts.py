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
        return "unknown"

    def get_system_info(self) -> ZeroApiResult:
        return ZeroApiResult(
            ok=False,
            op="get_system_info",
            backend=self.backend_name(),
            detail={"error": "get_system_info not implemented by backend"},
        )

    def list_processes(self, limit: int = 20) -> ZeroApiResult:
        return ZeroApiResult(
            ok=False,
            op="list_processes",
            backend=self.backend_name(),
            detail={
                "limit": max(1, int(limit)),
                "error": "list_processes not implemented by backend",
            },
        )

    def run_shell(self, command: str) -> ZeroApiResult:
        return ZeroApiResult(
            ok=False,
            op="run_shell",
            backend=self.backend_name(),
            detail={
                "command": str(command),
                "error": "run_shell not implemented by backend",
            },
        )
