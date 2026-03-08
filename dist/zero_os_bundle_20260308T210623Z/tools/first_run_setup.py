from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


def run(cmd: list[str], cwd: Path) -> tuple[int, str]:
    p = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True)
    out = (p.stdout or "") + ("\n" + p.stderr if p.stderr else "")
    return p.returncode, out.strip()


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    steps = [
        ["python", "src/main.py", "fix all now"],
        ["python", "src/main.py", "zero ai backup create"],
        ["python", "src/main.py", "enterprise security on"],
        ["python", "src/main.py", "enterprise policy lock apply"],
        ["python", "src/main.py", "triad ops on interval=60 sink=log+inbox"],
        ["python", "src/main.py", "self repair on interval=60"],
        ["python", "src/main.py", "antivirus monitor on interval=60"],
    ]

    logs = []
    ok = True
    for cmd in steps:
        code, out = run(cmd, root)
        logs.append({"cmd": " ".join(cmd), "ok": code == 0, "output": out[-2000:]})
        if code != 0:
            ok = False
        # Soft-fail if lane fallback appears, so onboarding can still complete.
        if "lane=fallback" in out.lower():
            logs[-1]["ok"] = False
            logs[-1]["fallback"] = True
            ok = False

    report = {
        "ok": ok,
        "cwd": str(root),
        "steps": logs,
        "next": {
            "shell_ui": str(root / "zero_os_shell.html"),
            "dashboard": str(root / "zero_os_dashboard.html"),
            "status_cmd": 'python src/main.py "security overview"',
        },
    }

    out_path = root / ".zero_os" / "runtime" / "first_run_report.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
