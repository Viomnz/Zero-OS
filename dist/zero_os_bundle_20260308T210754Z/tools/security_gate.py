from __future__ import annotations

import subprocess
import sys


def run(cmd: list[str]) -> int:
    print("running:", " ".join(cmd), flush=True)
    p = subprocess.run(cmd)
    if p.returncode != 0:
        print(f"failed: {' '.join(cmd)} (exit {p.returncode})", file=sys.stderr, flush=True)
    return p.returncode


def main() -> int:
    suites = [
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py", "-q"],
        [
            sys.executable,
            "-m",
            "unittest",
            "tests.test_antivirus_system",
            "tests.test_quantum_virus_curefirewall",
            "tests.test_security_integrity_layer",
            "-q",
        ],
    ]
    for cmd in suites:
        rc = run(cmd)
        if rc != 0:
            return rc
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
