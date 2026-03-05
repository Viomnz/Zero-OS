from __future__ import annotations

import platform
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
