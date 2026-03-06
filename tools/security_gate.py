from __future__ import annotations

import subprocess
import sys


def run(cmd: list[str]) -> int:
    p = subprocess.run(cmd)
    return p.returncode


def main() -> int:
    suites = [
        ["python", "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py", "-q"],
        [
            "python",
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
