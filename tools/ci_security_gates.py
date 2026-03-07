from __future__ import annotations

import subprocess


def _run(cmd: list[str]) -> int:
    return subprocess.run(cmd).returncode


def main() -> int:
    cmds = [
        ["python", "tools/security_gate.py"],
        ["python", "tools/sign_artifacts.py"],
        ["python", "tools/release_verify.py"],
        ["python", "-m", "unittest", "tests.test_security_integrity_layer", "tests.test_zero_ai_gate", "-q"],
    ]
    for cmd in cmds:
        rc = _run(cmd)
        if rc != 0:
            return rc
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
