from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def _run(cmd: list[str], cwd: Path) -> int:
    return int(subprocess.run(cmd, cwd=str(cwd)).returncode)


def main() -> int:
    root = Path(__file__).resolve().parent
    python_exe = sys.executable or "python"

    print("Zero OS QuickStart")
    print()
    print("Step 1: Running first-run setup...")
    code = _run([python_exe, str(root / "tools" / "first_run_setup.py")], root)
    if code != 0:
        print()
        print("First-run failed. Review the output above and try again.")
        return code

    print()
    print("Step 2: Opening Zero OS UI...")
    subprocess.Popen([python_exe, str(root / "zero_os_ui.py")], cwd=str(root))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
