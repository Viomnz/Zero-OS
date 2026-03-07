from __future__ import annotations

import platform
from pathlib import Path
import socket
import subprocess
from typing import Any

from zero_os.hyperlayer.contracts import ZeroApi, ZeroApiResult


class BaseAdapter(ZeroApi):
    def backend_name(self) -> str:
        return "base"

    def get_system_info(self) -> ZeroApiResult:
        return ZeroApiResult(
            ok=True,
            op="get_system_info",
            backend=self.backend_name(),
            detail={
                "system": platform.system(),
                "release": platform.release(),
                "version": platform.version(),
                "machine": platform.machine(),
                "processor": platform.processor(),
            },
        )

    def list_processes(self, limit: int = 20) -> ZeroApiResult:
        try:
            rows: list[dict[str, Any]] = []
            for p in subprocess.run(
                ["python", "-c", "import psutil, json; print('[]')"],
                capture_output=True,
                text=True,
                timeout=1,
            ).stdout.splitlines():
                _ = p
            cmd = [
                "powershell",
                "-NoProfile",
                "-Command",
                f"Get-Process | Select-Object -First {max(1, int(limit))} Id,ProcessName | ConvertTo-Json",
            ]
            out = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            data = out.stdout.strip() or "[]"
            return ZeroApiResult(
                ok=out.returncode == 0,
                op="list_processes",
                backend=self.backend_name(),
                detail={"raw": data},
            )
        except Exception as e:
            return ZeroApiResult(
                ok=False,
                op="list_processes",
                backend=self.backend_name(),
                detail={"error": str(e)},
            )

    def run_shell(self, command: str) -> ZeroApiResult:
        try:
            out = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=10,
            )
            return ZeroApiResult(
                ok=out.returncode == 0,
                op="run_shell",
                backend=self.backend_name(),
                detail={
                    "returncode": out.returncode,
                    "stdout": out.stdout[-4000:],
                    "stderr": out.stderr[-4000:],
                },
            )
        except Exception as e:
            return ZeroApiResult(
                ok=False,
                op="run_shell",
                backend=self.backend_name(),
                detail={"error": str(e)},
            )

    def list_files(self, path: str = ".", limit: int = 100) -> ZeroApiResult:
        try:
            root = Path(path).resolve()
            rows = []
            for p in sorted(root.iterdir())[: max(1, int(limit))]:
                rows.append({"name": p.name, "is_dir": p.is_dir()})
            return ZeroApiResult(
                ok=True,
                op="list_files",
                backend=self.backend_name(),
                detail={"path": str(root), "items": rows},
            )
        except Exception as e:
            return ZeroApiResult(False, "list_files", self.backend_name(), {"error": str(e)})

    def network_probe(self, host: str, port: int = 443, timeout: int = 3) -> ZeroApiResult:
        try:
            with socket.create_connection((host, int(port)), timeout=max(1, int(timeout))):
                pass
            return ZeroApiResult(
                ok=True,
                op="network_probe",
                backend=self.backend_name(),
                detail={"host": host, "port": int(port), "reachable": True},
            )
        except Exception as e:
            return ZeroApiResult(
                ok=False,
                op="network_probe",
                backend=self.backend_name(),
                detail={"host": host, "port": int(port), "reachable": False, "error": str(e)},
            )

    def package_runtime_status(self) -> ZeroApiResult:
        try:
            out = subprocess.run(
                ["python", "--version"],
                capture_output=True,
                text=True,
                timeout=3,
            )
            version = (out.stdout or out.stderr).strip()
            return ZeroApiResult(
                ok=out.returncode == 0,
                op="package_runtime_status",
                backend=self.backend_name(),
                detail={"python": version or "unknown"},
            )
        except Exception as e:
            return ZeroApiResult(False, "package_runtime_status", self.backend_name(), {"error": str(e)})

    def security_policy_backend(self) -> ZeroApiResult:
        return ZeroApiResult(
            ok=True,
            op="security_policy_backend",
            backend=self.backend_name(),
            detail={"model": "host_os_policy_bridge", "enforcement_level": "user-space"},
        )
