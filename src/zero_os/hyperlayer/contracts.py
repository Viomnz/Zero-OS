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

    def list_files(self, path: str = ".", limit: int = 100) -> ZeroApiResult:
        return ZeroApiResult(
            ok=False,
            op="list_files",
            backend=self.backend_name(),
            detail={
                "path": str(path),
                "limit": max(1, int(limit)),
                "error": "list_files not implemented by backend",
            },
        )

    def network_probe(self, host: str, port: int = 443, timeout: int = 3) -> ZeroApiResult:
        return ZeroApiResult(
            ok=False,
            op="network_probe",
            backend=self.backend_name(),
            detail={
                "host": str(host),
                "port": int(port),
                "timeout": int(timeout),
                "error": "network_probe not implemented by backend",
            },
        )

    def package_runtime_status(self) -> ZeroApiResult:
        return ZeroApiResult(
            ok=False,
            op="package_runtime_status",
            backend=self.backend_name(),
            detail={"error": "package_runtime_status not implemented by backend"},
        )

    def security_policy_backend(self) -> ZeroApiResult:
        return ZeroApiResult(
            ok=False,
            op="security_policy_backend",
            backend=self.backend_name(),
            detail={"error": "security_policy_backend not implemented by backend"},
        )
