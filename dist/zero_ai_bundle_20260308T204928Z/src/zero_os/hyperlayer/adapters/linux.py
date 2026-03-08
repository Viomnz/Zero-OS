from __future__ import annotations

import subprocess

from zero_os.hyperlayer.adapters.base import BaseAdapter
from zero_os.hyperlayer.contracts import ZeroApiResult


class LinuxAdapter(BaseAdapter):
    def backend_name(self) -> str:
        return "linux"

    def list_processes(self, limit: int = 20) -> ZeroApiResult:
        try:
            out = subprocess.run(
                ["ps", "-eo", "pid,comm", "--no-headers"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            rows = [ln.strip() for ln in out.stdout.splitlines() if ln.strip()][: max(1, int(limit))]
            return ZeroApiResult(
                ok=out.returncode == 0,
                op="list_processes",
                backend=self.backend_name(),
                detail={"rows": rows},
            )
        except Exception as e:
            return ZeroApiResult(False, "list_processes", self.backend_name(), {"error": str(e)})
